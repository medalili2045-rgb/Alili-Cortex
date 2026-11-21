import tempfile
import unittest
from pathlib import Path

from alili_engine.evolution import ACEvolutionEngine


class EvolutionEngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = ACEvolutionEngine(Path(self.tmp.name) / "evolution.sqlite3")

    def tearDown(self):
        self.tmp.cleanup()

    def test_proposal_is_quarantined_until_review(self):
        item = self.engine.propose(
            proposal_type="knowledge_library", item_id="ac_neuro_library",
            name="Neuroscience Knowledge", domain="biology",
            rationale="A verified knowledge gap was identified.",
            evidence_refs=["https://example.org/research"])
        self.assertEqual(item["status"], "pending_review")
        self.assertEqual(self.engine.status()["proposal_counts"]["pending_review"], 1)

    def test_brain_proposal_does_not_activate_brain(self):
        item = self.engine.propose(
            proposal_type="specialist_brain", item_id="ac_neuro_brain",
            name="Neuroscience Brain", domain="biology",
            rationale="Specialist coverage is needed.",
            evidence_refs=["https://example.org/brain"])
        reviewed = self.engine.review(item["proposal_id"], decision="approve",
                                      reviewer="human-reviewer", notes="Evidence checked")
        self.assertEqual(reviewed["status"], "approved")
        self.assertFalse(self.engine.status()["automatic_brain_activation"])

    def test_invalid_or_duplicate_proposals_fail_closed(self):
        kwargs = dict(proposal_type="knowledge_library", item_id="ac_new_lib",
                      name="New Library", domain="biology", rationale="Gap",
                      evidence_refs=["https://example.org"])
        self.engine.propose(**kwargs)
        with self.assertRaises(ValueError):
            self.engine.propose(**kwargs)
        with self.assertRaises(ValueError):
            self.engine.propose(**{**kwargs, "item_id": "bad id"})

    def test_evidence_must_be_https(self):
        with self.assertRaises(ValueError):
            self.engine.propose(
                proposal_type="specialist_brain", item_id="ac_new_brain",
                name="New Brain", domain="biology", rationale="Gap",
                evidence_refs=["http://example.org"])


if __name__ == "__main__":
    unittest.main()
