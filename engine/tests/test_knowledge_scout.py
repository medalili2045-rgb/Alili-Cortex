import os
import tempfile
import unittest

from alili_engine.knowledge_scout import KnowledgeScout, validate_public_https_url


class KnowledgeScoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.scout = KnowledgeScout(os.path.join(self.temp.name, "scout.sqlite3"))

    def tearDown(self):
        self.temp.cleanup()

    def register(self, terms_reviewed=True):
        return self.scout.register_source(
            source_id="python-docs", name="Python Documentation",
            base_url="https://docs.python.org", source_type="official_docs",
            domains=["software"], brains=["code", "learning_factory"],
            terms_reviewed=terms_reviewed)

    def test_url_policy_accepts_public_https_and_rejects_unsafe_targets(self):
        self.assertEqual(validate_public_https_url("https://docs.python.org/3/"), "https://docs.python.org/3/")
        for url in ("http://example.com", "https://localhost", "https://127.0.0.1",
                    "https://10.0.0.1", "https://example.com:8443",
                    "https://user:pass@example.com", "file:///etc/passwd"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_public_https_url(url)

    def test_sources_start_disabled_and_require_terms_evidence_to_enable(self):
        source = self.register()
        self.assertFalse(source["enabled"])
        with self.assertRaises(ValueError):
            self.scout.set_source_enabled("python-docs", True)
        enabled = self.scout.set_source_enabled(
            "python-docs", True, terms_evidence_url="https://docs.python.org/3/license.html")
        self.assertTrue(enabled["enabled"])

    def test_unreviewed_source_cannot_be_enabled(self):
        self.register(terms_reviewed=False)
        with self.assertRaisesRegex(ValueError, "source_terms_review_required"):
            self.scout.set_source_enabled(
                "python-docs", True, terms_evidence_url="https://docs.python.org/3/license.html")

    def test_jobs_are_resumable_and_checkpointed(self):
        self.register()
        self.scout.set_source_enabled(
            "python-docs", True, terms_evidence_url="https://docs.python.org/3/license.html")
        job = self.scout.enqueue(source_id="python-docs", query="Python async patterns")
        self.assertEqual(job["status"], "queued")
        paused = self.scout.checkpoint_job(
            job["job_id"], checkpoint={"cursor": "chapter-4", "visited": 12})
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(paused["attempts"], 1)
        self.assertEqual(paused["checkpoint"]["cursor"], "chapter-4")

    def test_proposals_keep_provenance_and_remain_quarantined(self):
        self.register()
        item = self.scout.propose(
            source_id="python-docs", title="Async programming",
            note="Use structured concurrency to manage related tasks.",
            domain="software", brain_id="code",
            source_url="https://docs.python.org/3/library/asyncio-task.html",
            license_evidence_url="https://docs.python.org/3/license.html")
        self.assertEqual(item["status"], "quarantined")
        self.assertEqual(item["provenance"]["source_id"], "python-docs")
        self.assertEqual(len(item["provenance"]["content_sha256"]), 64)
        self.assertFalse(item["install_enabled"])

    def test_proposal_cannot_escape_registered_source_or_scope(self):
        self.register()
        with self.assertRaisesRegex(ValueError, "proposal_url_outside_registered_source"):
            self.scout.propose(
                source_id="python-docs", title="Bad", note="Short note",
                domain="software", brain_id="code",
                source_url="https://example.org/copied")
        with self.assertRaises(ValueError):
            self.scout.propose(
                source_id="python-docs", title="Bad", note="Short note",
                domain="security_defense", brain_id="code",
                source_url="https://docs.python.org/3/")

    def test_duplicate_notes_are_rejected_by_content_fingerprint(self):
        self.register()
        args = dict(source_id="python-docs", title="Note", note="Identical short note",
                    domain="software", brain_id="code", source_url="https://docs.python.org/3/")
        self.scout.propose(**args)
        with self.assertRaises(Exception):
            self.scout.propose(**args)

    def test_no_network_or_automatic_learning_is_claimed(self):
        status = self.scout.summary()
        self.assertEqual(status["network_fetch"], "not_implemented")
        self.assertEqual(status["discovery_execution"], "not_enabled")
        self.assertFalse(status["continuous_uptime_guaranteed"])
        self.assertFalse(status["automatic_publication"])


if __name__ == "__main__":
    unittest.main()
