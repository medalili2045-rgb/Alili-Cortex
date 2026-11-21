import hashlib
import tempfile
import unittest
from pathlib import Path

from alili_engine.autonomous_worker import AutonomousLearningWorker


class FakeConnector:
    def __init__(self):
        self.calls = 0

    def fetch(self, source_id, if_none_match=None, if_modified_since=None):
        self.calls += 1
        if if_none_match == '"etag-1"':
            return {"not_modified": True, "etag": '"etag-1"',
                    "last_modified": "Wed, 01 Jan 2025 00:00:00 GMT"}
        content = "API interface and safety constraints."
        return {
            "title": "Official guide", "content": content,
            "artifact_url": "https://docs.example.org/guide",
            "version": "v1", "etag": '"etag-1"',
            "last_modified": "Wed, 01 Jan 2025 00:00:00 GMT",
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }


class FakeService:
    def __init__(self):
        self.connectors = FakeConnector()
        self.proposals = []
        self.evidence = []
        self.fail_session_once = False
        self.sources = [
            {"source_id": "source_one", "name": "Source One", "domains": ["ai"],
             "study_focus": ["API interfaces", "safety"]},
            {"source_id": "source_two", "name": "Source Two", "domains": ["code"],
             "study_focus": ["testing"]},
        ]

    def ecosystem_catalog(self, limit=200):
        return self.sources[:limit]

    def add_study_evidence(self, **kwargs):
        item = {**kwargs, "evidence_id": "evidence-" + kwargs["source_id"],
                "sha256": hashlib.sha256(kwargs["content"].encode("utf-8")).hexdigest(),
                "status": "quarantined"}
        self.evidence.append(item)
        return item

    def list_study_evidence(self, source_id=None, limit=50):
        return [{key: item[key] for key in ("evidence_id", "source_id", "sha256", "status")}
                for item in self.evidence if source_id is None or item["source_id"] == source_id][:limit]

    def get_study_evidence(self, evidence_id):
        return next((item for item in self.evidence if item["evidence_id"] == evidence_id), None)

    def create_study_session(self, **kwargs):
        if self.fail_session_once:
            self.fail_session_once = False
            raise RuntimeError("temporary session failure")
        return {"session_id": "session-1"}

    def evaluate_study_session(self, session_id):
        return {"evaluation": {
            "status": "blocked_pending_license_provenance_or_relevance"}}

    def propose_study_knowledge(self, session_id, **kwargs):
        self.proposals.append(session_id)
        return {"artifact_id": "proposed-1"}


class AutonomousLearningWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp.name) / "worker.sqlite3")
        self.service = FakeService()
        self.worker = AutonomousLearningWorker(
            self.service, self.db_path, interval_seconds=86400, max_documents=1)

    def tearDown(self):
        self.temp.cleanup()

    def test_cycle_studies_bounded_number_but_keeps_unreviewed_evidence_quarantined(self):
        result = self.worker.run_cycle()
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["fetched"], 1)
        self.assertEqual(result["studied"], 1)
        self.assertEqual(result["proposed"], 0)
        self.assertEqual(self.service.proposals, [])
        self.assertEqual(self.service.evidence[0]["status"], "quarantined")
        self.assertEqual(self.service.evidence[0]["license_status"], "review_required")
        self.assertEqual(self.worker.status()["publication"], "human_approval_required")

    def test_etag_unchanged_document_is_skipped(self):
        self.worker.run_cycle()
        self.service.sources = self.service.sources[:1]
        result = self.worker.run_cycle()
        self.assertEqual(result["fetched"], 0)
        self.assertEqual(result["skipped"], 1)

    def test_pause_prevents_study_cycle(self):
        self.worker.set_paused(True)
        result = self.worker.run_cycle()
        self.assertEqual(result["status"], "paused")
        self.assertEqual(self.service.connectors.calls, 0)

    def test_cycle_lease_can_be_refreshed_by_its_owner(self):
        self.assertTrue(self.worker._acquire_lock())
        self.assertTrue(self.worker._refresh_lock())
        self.worker._release_lock()
        self.assertFalse(self.worker._refresh_lock())

    def test_failed_session_retry_reuses_existing_evidence(self):
        self.service.sources = self.service.sources[:1]
        self.service.fail_session_once = True
        first = self.worker.run_cycle()
        self.assertEqual(first["status"], "completed_with_errors")
        self.assertEqual(len(self.service.evidence), 1)
        second = self.worker.run_cycle()
        self.assertEqual(second["status"], "completed")
        self.assertEqual(len(self.service.evidence), 1)

    def test_checkpoint_uses_full_source_digest_not_truncated_evidence_digest(self):
        long_content = "x" * 70000
        full_digest = hashlib.sha256(long_content.encode("utf-8")).hexdigest()
        self.service.connectors.fetch = lambda *args, **kwargs: {
            "title": "Large guide", "content": long_content,
            "artifact_url": "https://docs.example.org/large", "version": "v1",
            "etag": '"large-1"', "last_modified": None, "sha256": full_digest,
        }
        source = self.service.sources[0]
        self.worker._study_source(source)
        self.assertEqual(self.worker._source_checkpoint(source["source_id"])["content_sha256"],
                         full_digest)
        self.assertNotEqual(self.service.evidence[0]["sha256"], full_digest)

    def test_outer_cycle_failure_is_recorded_as_failed(self):
        self.service.ecosystem_catalog = lambda limit=200: (_ for _ in ()).throw(
            RuntimeError("catalog unavailable"))
        with self.assertRaisesRegex(RuntimeError, "catalog unavailable"):
            self.worker.run_cycle()
        self.assertEqual(self.worker.status()["last_cycle_status"], "failed")
        self.assertEqual(self.worker.status()["latest_run"]["status"], "failed")

    def test_source_failure_is_reported_in_cycle_status(self):
        class BrokenConnector:
            def fetch(self, *args, **kwargs):
                raise RuntimeError("source unavailable")

        self.service.connectors = BrokenConnector()
        result = self.worker.run_cycle()
        self.assertEqual(result["status"], "completed_with_errors")
        self.assertEqual(len(result["errors"]), 2)

    def test_invalid_cycle_limits_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "max_documents"):
            AutonomousLearningWorker(self.service, self.db_path,
                                     interval_seconds=86400, max_documents=0)
        with self.assertRaisesRegex(ValueError, "interval_seconds"):
            AutonomousLearningWorker(self.service, self.db_path,
                                     interval_seconds=60, max_documents=1)


if __name__ == "__main__":
    unittest.main()
