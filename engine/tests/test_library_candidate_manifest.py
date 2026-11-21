import json
import unittest
from pathlib import Path


class LibraryCandidateManifestTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parents[1] / "data" / "library_candidates.json"
        self.manifest = json.loads(path.read_text(encoding="utf-8"))

    def test_manifest_is_curated_and_nonempty(self):
        self.assertEqual(self.manifest["schema_version"], "1.0.0")
        self.assertGreaterEqual(len(self.manifest["candidates"]), 15)

    def test_candidate_ids_are_unique(self):
        ids = [item["library_id"] for item in self.manifest["candidates"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_candidate_is_quarantined_and_not_installable(self):
        for item in self.manifest["candidates"]:
            self.assertEqual(item["admission_status"], "quarantined")
            self.assertFalse(item["install_enabled"])
            self.assertIsNone(item["artifact_sha256"])

    def test_every_candidate_has_provenance_and_license_evidence_pointer(self):
        for item in self.manifest["candidates"]:
            self.assertTrue(item["source_url"].startswith("https://"))
            self.assertTrue(item["license_evidence_url"].startswith("https://"))
            self.assertEqual(item["version"], "unresolved")
            self.assertIn("verify_dependency_licenses", item["review_required"])

    def test_policy_is_free_only_and_fail_closed(self):
        policy = self.manifest["policy"]
        self.assertTrue(policy["free_only"])
        self.assertFalse(policy["paid_services_allowed"])
        self.assertFalse(policy["bank_card_required"])
        self.assertFalse(policy["automatic_installation"])
        self.assertFalse(policy["automatic_approval"])


if __name__ == "__main__":
    unittest.main()
