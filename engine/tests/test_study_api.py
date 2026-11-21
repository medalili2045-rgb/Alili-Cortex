import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from alili_engine.api import create_handler
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class ACStudyApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        service = EngineService(TaskStore(self.temp.name + "/engine.sqlite3"))
        self.token = "ac-study-api-test-token-longer-than-32-chars"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(service, self.token))
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
        with urlopen(request) as response:
            return response.status, json.loads(response.read())

    def test_evidence_study_evaluation_and_knowledge_proposal_flow(self):
        status, payload = self.request_json("/v1/study/evidence", {
            "source_id": "hf_transformers",
            "title": "Local documentation excerpt",
            "content": "Transformers expose model architectures and tokenizers.",
            "artifact_url": "https://huggingface.co/docs/transformers",
            "version": "pinned-test-version",
            "license_status": "approved",
        })
        self.assertEqual(status, 202)
        evidence_id = payload["evidence"]["evidence_id"]
        self.assertEqual(payload["evidence"]["status"], "quarantined")

        status, payload = self.request_json("/v1/study/sessions", {
            "question": "Study model architectures and tokenizers",
            "domain": "language",
            "evidence_ids": [evidence_id],
        })
        self.assertEqual(status, 201)
        session_id = payload["session"]["session_id"]

        status, payload = self.request_json(f"/v1/study/sessions/{session_id}/evaluate", {})
        self.assertEqual(status, 200)
        self.assertEqual(payload["session"]["evaluation"]["status"],
                         "structural_checks_passed_human_review_required")

        status, payload = self.request_json(
            f"/v1/study/sessions/{session_id}/propose-knowledge", {})
        self.assertEqual(status, 201)
        self.assertEqual(payload["artifact"]["status"], "proposed")
        self.assertEqual(payload["artifact"]["license_id"], "review_required")

        status, payload = self.request_json(
            f"/v1/knowledge/{payload['artifact']['artifact_id']}/transition", {
                "status": "quarantined",
            })
        self.assertEqual(status, 200)
        self.assertEqual(payload["artifact"]["status"], "quarantined")

        status, payload = self.request_json(
            f"/v1/knowledge/{payload['artifact']['artifact_id']}/transition", {
                "status": "validated", "reviewer_id": "local-owner",
                "review_note": "Reviewed the source license and provenance.",
                "license_decision": "approved",
            })
        self.assertEqual(status, 200)
        self.assertEqual(payload["artifact"]["status"], "validated")
        self.assertEqual(payload["artifact"]["license_id"], "approved")
        self.assertEqual(payload["artifact"]["metadata"]["human_reviews"][0]["reviewer_id"],
                         "local-owner")

        status, payload = self.request_json(
            f"/v1/knowledge/{payload['artifact']['artifact_id']}/transition", {
                "status": "approved", "reviewer_id": "local-owner",
                "review_note": "Reviewed the study result.",
            })
        self.assertEqual(status, 200)
        self.assertEqual(payload["artifact"]["status"], "approved")

        status, payload = self.request_json(
            f"/v1/knowledge/{payload['artifact']['artifact_id']}/transition", {
                "status": "published", "reviewer_id": "local-owner",
                "review_note": "Approved for publication.",
            })
        self.assertEqual(status, 200)
        self.assertEqual(payload["artifact"]["status"], "published")

    def test_review_required_license_cannot_pass_study_evaluation(self):
        _, evidence_payload = self.request_json("/v1/study/evidence", {
            "source_id": "hf_transformers", "title": "Unreviewed excerpt",
            "content": "Transformers provide model architectures.",
            "license_status": "review_required",
        })
        evidence_id = evidence_payload["evidence"]["evidence_id"]
        _, session_payload = self.request_json("/v1/study/sessions", {
            "question": "Study model architectures", "evidence_ids": [evidence_id],
        })
        session_id = session_payload["session"]["session_id"]
        _, evaluated = self.request_json(f"/v1/study/sessions/{session_id}/evaluate", {})
        self.assertEqual(evaluated["session"]["evaluation"]["status"],
                         "blocked_pending_license_provenance_or_relevance")

    def test_evidence_listing_does_not_expose_content(self):
        self.request_json("/v1/study/evidence", {
            "source_id": "hf_transformers", "title": "Excerpt",
            "content": "private local excerpt"
        })
        status, payload = self.request_json("/v1/study/evidence")
        self.assertEqual(status, 200)
        self.assertNotIn("content", payload["evidence"][0])

    def test_study_endpoints_require_authentication(self):
        request = Request(self.base + "/v1/study/evidence")
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 401)


if __name__ == "__main__":
    unittest.main()
