import tempfile
import unittest
from pathlib import Path

from alili_engine.observatory import AICapabilityObservatory


class AICapabilityObservatoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.observatory = AICapabilityObservatory(
            str(Path(self.temp.name) / "observatory.sqlite3"))

    def tearDown(self):
        self.temp.cleanup()

    def test_catalog_includes_ai_studio_nano_banana_and_copilot(self):
        catalog = {item["id"]: item for item in self.observatory.catalog()}
        self.assertIn("google_ai_studio", catalog)
        self.assertIn("google_nano_banana", catalog)
        self.assertIn("github_copilot", catalog)
        copilot = catalog["github_copilot"]
        self.assertIn("code_review", copilot["capabilities"])
        self.assertIn("multi_step_coding_agent", copilot["capabilities"])
        self.assertIn("repository_instructions", copilot["study_focus"])

    def test_catalog_filtering_and_bounds(self):
        results = self.observatory.catalog(category="software_engineering_assistant")
        self.assertEqual([item["id"] for item in results], ["github_copilot"])
        self.assertEqual(self.observatory.catalog(query="Nano Banana")[0]["id"],
                         "google_nano_banana")
        with self.assertRaisesRegex(ValueError, "limit_must"):
            self.observatory.catalog(limit=0)

    def test_study_is_persisted_but_quarantined_and_license_unapproved(self):
        study = self.observatory.record_study(
            "github_copilot", "Repository agent workflow",
            "Study task planning, patch review and human approval.",
            "https://docs.github.com/en/copilot")
        self.assertEqual(study["status"], "quarantined")
        self.assertEqual(study["license_status"], "review_required")
        self.assertEqual(self.observatory.list_studies()[0]["study_id"], study["study_id"])

    def test_unknown_capability_and_invalid_notes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown_ai_capability"):
            self.observatory.record_study("made_up", "x", "y", "https://example.org")
        with self.assertRaisesRegex(ValueError, "invalid_notes"):
            self.observatory.record_study("github_copilot", "title", " ", "https://docs.github.com")

    def test_response_style_reports_structural_checks_not_truth(self):
        result = self.observatory.evaluate_response(
            "Yes, this is possible.\n\nWe can split it into three independent steps.")
        self.assertEqual(result["profile"], "ac_clear_response_v1")
        self.assertEqual(result["structural_score"], 1.0)
        self.assertEqual(result["semantic_accuracy"], "not_evaluated")
        self.assertTrue(result["human_review_required"])

    def test_response_style_flags_repetition_and_overlong_sentence(self):
        result = self.observatory.evaluate_response(
            ("This is one repeated line.\nThis is one repeated line.\n" +
             " ".join(["word"] * 60)))
        self.assertFalse(result["checks"]["limited_repetition"])
        self.assertFalse(result["checks"]["reasonable_sentence_length"])
        self.assertGreater(len(result["suggestions"]), 0)


if __name__ == "__main__":
    unittest.main()
