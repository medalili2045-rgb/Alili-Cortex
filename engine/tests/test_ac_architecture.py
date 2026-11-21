import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from alili_engine.api import create_handler
from alili_engine.brains import BrainManifest, BrainRegistry, BrainRouter
from alili_engine.knowledge import KnowledgeStore
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class BrainRegistryTests(unittest.TestCase):
    def test_default_brains_are_registered_but_not_claimed_operational(self):
        registry = BrainRegistry()
        self.assertEqual(len(registry.all()), 10)
        self.assertTrue(all(item["status"] == "planned" for item in registry.all()))

    def test_duplicate_brain_id_is_rejected(self):
        brain = BrainManifest("custom", "Custom", "1.0", ("test",), ("test",))
        with self.assertRaises(ValueError):
            BrainRegistry((brain, brain))

    def test_router_selects_logical_brain_without_execution(self):
        router = BrainRouter(BrainRegistry())
        decision = router.route("code")
        self.assertEqual(decision.brain_id, "ac_code")
        self.assertFalse(decision.executable)
        self.assertEqual(decision.status, "planned")

    def test_unknown_task_type_is_not_routed(self):
        decision = BrainRouter(BrainRegistry()).route("unknown_task")
        self.assertIsNone(decision.brain_id)
        self.assertFalse(decision.executable)


class KnowledgeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = KnowledgeStore(
            os.path.join(self.temp.name, "knowledge.sqlite3"),
            source_validator=lambda source_id: source_id == "evidence-1")

    def tearDown(self):
        self.temp.cleanup()

    def propose(self, sources=None):
        return self.store.propose(
            artifact_type="fact",
            title="Local test artifact",
            content="A test fact with traceable provenance.",
            origin_brain="ac_research",
            origin_version="1.0.0",
            sources=sources if sources is not None else ["evidence-1"],
            license_id="review_required",
            confidence=0.8,
        )

    def test_artifact_must_follow_quarantine_validation_and_approval(self):
        artifact = self.propose()
        self.assertEqual(artifact["status"], "proposed")
        with self.assertRaises(ValueError):
            self.store.transition(artifact["artifact_id"], "published")
        artifact = self.store.transition(artifact["artifact_id"], "quarantined")
        artifact = self.store.transition(
            artifact["artifact_id"], "validated", reviewer_id="test-owner",
            review_note="Verified evidence provenance and license terms.",
            license_decision="approved")
        artifact = self.store.transition(
            artifact["artifact_id"], "approved", reviewer_id="test-owner",
            review_note="Reviewed artifact quality.")
        artifact = self.store.transition(
            artifact["artifact_id"], "published", reviewer_id="test-owner",
            review_note="Approved for publication.")
        self.assertEqual(artifact["status"], "published")

    def test_artifact_without_sources_cannot_be_validated(self):
        artifact = self.propose(sources=[])
        artifact = self.store.transition(artifact["artifact_id"], "quarantined")
        with self.assertRaisesRegex(ValueError, "requires_source"):
            self.store.transition(
                artifact["artifact_id"], "validated", reviewer_id="test-owner",
                review_note="Attempt validation without sources.", license_decision="approved")

    def test_published_artifact_can_be_superseded_but_not_reopened(self):
        artifact = self.propose()
        for status in ("quarantined", "validated", "approved", "published"):
            review = ({"reviewer_id": "test-owner", "review_note": "Reviewed lifecycle step.",
                       "license_decision": "approved"} if status == "validated" else
                      {"reviewer_id": "test-owner", "review_note": "Reviewed lifecycle step."}
                      if status in {"approved", "published"} else {})
            artifact = self.store.transition(artifact["artifact_id"], status, **review)
        artifact = self.store.transition(artifact["artifact_id"], "superseded")
        self.assertEqual(artifact["status"], "superseded")
        with self.assertRaises(ValueError):
            self.store.transition(artifact["artifact_id"], "published")

    def test_invalid_confidence_is_rejected(self):
        with self.assertRaises(ValueError):
            self.store.propose(
                artifact_type="fact", title="bad", content="bad",
                origin_brain="ac_research", origin_version="1",
                sources=[], license_id="unknown", confidence=2,
            )


class BrainAndKnowledgeApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        store = TaskStore(os.path.join(self.temp.name, "engine.sqlite3"))
        service = EngineService(store)
        self.token = "ac-test-token-that-is-longer-than-32-chars"
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
        data = json.dumps(body).encode() if body is not None else None
        request = Request(
            self.base + path,
            data=data,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            method="POST" if body is not None else "GET",
        )
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as response:
            return response.code, json.loads(response.read())

    def test_brain_registry_endpoint(self):
        status, payload = self.request_json("/v1/brains")
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["brains"]), 10)
        self.assertFalse(payload["execution_enabled"])

    def test_router_endpoint_never_claims_execution(self):
        status, payload = self.request_json("/v1/route", {"task_type": "code"})
        self.assertEqual(status, 200)
        self.assertEqual(payload["route"]["brain_id"], "ac_code")
        self.assertFalse(payload["route"]["executable"])

    def test_unverified_external_source_cannot_be_validated_or_published(self):
        status, payload = self.request_json("/v1/knowledge", {
            "artifact_type": "method",
            "title": "Test method",
            "content": "A reusable method.",
            "origin_brain": "ac_code",
            "origin_version": "1.0.0",
            "sources": ["https://example.invalid/method"],
            "license_id": "MIT",
            "confidence": 0.7,
        })
        self.assertEqual(status, 201)
        artifact_id = payload["artifact"]["artifact_id"]
        status, payload = self.request_json(
            f"/v1/knowledge/{artifact_id}/transition", {"status": "quarantined"})
        self.assertEqual(status, 200)
        status, payload = self.request_json(
            f"/v1/knowledge/{artifact_id}/transition", {
                "status": "validated", "reviewer_id": "local-owner",
                "review_note": "Attempted validation without registered evidence.",
                "license_decision": "approved",
            })
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "restricted_or_unknown_license_blocks_validation")
        status, payload = self.request_json("/v1/knowledge?status=published")
        self.assertEqual(status, 200)
        self.assertEqual(payload["artifacts"], [])


if __name__ == "__main__":
    unittest.main()
