import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

from alili_engine.api import create_handler
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class ACSourceLinkApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = EngineService(TaskStore(self.temp.name + "/engine.sqlite3"))
        self.token = "ac-source-link-api-test-token-longer-than-32-chars"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(self.service, self.token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request_json(self, path, body=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(self.base + path, data=data,
                          headers={"Authorization": "Bearer " + self.token,
                                   "Content-Type": "application/json"},
                          method="POST" if body is not None else "GET")
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as response:
            return response.code, json.loads(response.read())

    def test_connector_intake_creates_quarantined_evidence_and_source_link(self):
        fetched = {
            "source_id": "hf_transformers", "title": "README.md",
            "artifact_url": "https://github.com/huggingface/transformers/README.md",
            "version": '"etag-1"', "retrieved_at": "2026-11-20T00:00:00+00:00",
            "content_type": "text/markdown", "content": "Transformers documentation excerpt.",
            "sha256": "a" * 64, "etag": '"etag-1"', "last_modified": None,
            "license_status": "review_required", "status": "quarantined", "redirect_count": 0,
        }
        with patch.object(self.service.connectors, "fetch", return_value=fetched):
            status, payload = self.request_json("/v1/connectors/fetch", {
                "source_id": "hf_transformers"
            })
        self.assertEqual(status, 202)
        evidence = payload["evidence"]
        self.assertEqual(evidence["status"], "quarantined")
        self.assertEqual(evidence["license_status"], "review_required")
        self.assertEqual(payload["link"]["relation"], "documents")
        status, links = self.request_json(
            "/v1/links?node_type=evidence&node_id=" + evidence["evidence_id"])
        self.assertEqual(status, 200)
        self.assertEqual(len(links["links"]), 1)

    def test_evidence_session_knowledge_and_brain_are_linked_automatically(self):
        evidence = self.service.add_study_evidence(
            source_id="hf_transformers", title="API excerpt",
            content="Transformers model architectures and tokenizers.",
            license_status="approved")
        session = self.service.create_study_session(
            question="Study model architectures and tokenizers",
            evidence_ids=[evidence["evidence_id"]], domain="language")
        self.service.evaluate_study_session(session["session_id"])
        artifact = self.service.propose_study_knowledge(session["session_id"])
        links = self.service.list_links(limit=100)
        edges = {(item["source_type"], item["relation"], item["target_type"])
                 for item in links}
        self.assertIn(("source", "documents", "evidence"), edges)
        self.assertIn(("evidence", "studied_in", "session"), edges)
        self.assertIn(("session", "proposes", "knowledge"), edges)
        self.assertIn(("evidence", "supports", "knowledge"), edges)
        self.assertIn(("knowledge", "assigned_to", "brain"), edges)
        self.assertEqual(artifact["status"], "proposed")

    def test_evidence_and_provenance_link_roll_back_together_on_link_failure(self):
        with patch.object(self.service.links, "add", side_effect=RuntimeError("link store unavailable")):
            with self.assertRaisesRegex(RuntimeError, "link store unavailable"):
                self.service.add_study_evidence(
                    source_id="hf_transformers", title="Atomic test",
                    content="Evidence must not survive without its provenance link.",
                    license_status="review_required")
        self.assertEqual(self.service.list_study_evidence(source_id="hf_transformers"), [])

    def test_api_rejects_transfer_encoding_without_content_length(self):
        import http.client
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        connection.putrequest("POST", "/v1/tasks")
        connection.putheader("Authorization", "Bearer " + self.token)
        connection.putheader("Transfer-Encoding", "chunked")
        connection.endheaders()
        response = connection.getresponse()
        payload = json.loads(response.read())
        connection.close()
        self.assertEqual(response.status, 400)
        self.assertEqual(payload["error"], "transfer_encoding_not_supported")

    def test_study_session_and_evidence_links_roll_back_together(self):
        evidence = self.service.add_study_evidence(
            source_id="hf_transformers", title="Session transaction",
            content="Transformers architecture and tokenization.", license_status="approved")
        with patch.object(self.service.links, "add", side_effect=RuntimeError("link write failed")):
            with self.assertRaisesRegex(RuntimeError, "link write failed"):
                self.service.create_study_session(
                    question="Study transformers architecture",
                    evidence_ids=[evidence["evidence_id"]], domain="language")
        self.assertEqual(self.service.list_study_sessions(), [])

    def test_knowledge_proposal_and_provenance_links_roll_back_together(self):
        evidence = self.service.add_study_evidence(
            source_id="hf_transformers", title="Proposal transaction",
            content="Transformers architecture and tokenization.", license_status="approved")
        session = self.service.create_study_session(
            question="Study transformers architecture",
            evidence_ids=[evidence["evidence_id"]], domain="language")
        self.service.evaluate_study_session(session["session_id"])
        with patch.object(self.service.links, "add", side_effect=RuntimeError("link write failed")):
            with self.assertRaisesRegex(RuntimeError, "link write failed"):
                self.service.propose_study_knowledge(session["session_id"])
        self.assertEqual(self.service.list_knowledge(), [])

    def test_link_endpoint_checks_both_endpoints_and_relation(self):
        status, payload = self.request_json("/v1/links", {
            "source_type": "source", "source_id": "hf_transformers",
            "relation": "documents", "target_type": "evidence", "target_id": "missing"
        })
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "link_target_node_not_found")

    def test_link_endpoints_require_authentication(self):
        request = Request(self.base + "/v1/links")
        with self.assertRaises(Exception):
            urlopen(request)


if __name__ == "__main__":
    unittest.main()
