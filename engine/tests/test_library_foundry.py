import tempfile
import unittest
from pathlib import Path

from alili_engine.library_foundry import LibraryFoundry


class LibraryFoundryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.foundry = LibraryFoundry(Path(self.temp.name) / "ac-test.db")

    def tearDown(self):
        self.temp.cleanup()

    def register(self, **overrides):
        values = {
            "library_id": "numpy-core",
            "name": "NumPy",
            "version": "2.1.0",
            "ecosystem": "pypi",
            "source_url": "https://github.com/numpy/numpy",
            "license_id": "BSD-3-Clause",
            "artifact": b"package metadata sample",
            "domains": ["math", "science"],
            "brains": ["science", "code"],
        }
        values.update(overrides)
        return self.foundry.register(**values)

    def test_new_entry_is_quarantined_by_default(self):
        item = self.register()
        self.assertEqual(item["status"], "quarantined")
        self.assertEqual(item["license_status"], "review_required")
        self.assertEqual(self.foundry.summary()["installations"], 0)

    def test_explicit_license_evidence_can_approve_at_registration(self):
        item = self.register(license_approval={
            "reviewed": True, "artifact_scope": "package",
            "reviewer": "AC reviewer",
            "evidence_ref": "https://github.com/numpy/numpy/blob/main/LICENSE.txt",
        })
        self.assertEqual(item["status"], "approved")

    def test_unknown_license_cannot_be_approved(self):
        item = self.register(license_id="UNKNOWN")
        with self.assertRaisesRegex(ValueError, "license_not_in_allowlist"):
            self.foundry.review(item["library_id"], decision="approve",
                                reviewer="reviewer", evidence_ref="https://example.org/license", artifact_scope="package")

    def test_duplicate_artifact_is_rejected(self):
        self.register()
        with self.assertRaisesRegex(ValueError, "duplicate_artifact"):
            self.register(library_id="numpy-copy")

    def test_fingerprint_is_stable(self):
        a = self.foundry.fingerprint(b"AC")
        b = self.foundry.fingerprint(b"AC")
        self.assertEqual(a, b)
        self.assertEqual(a["size_bytes"], 2)
        self.assertEqual(len(a["sha256"]), 64)

    def test_brain_mapping_and_filters(self):
        self.register()
        self.assertEqual(len(self.foundry.list(domain="science")), 1)
        self.assertEqual(len(self.foundry.list(brain="code")), 1)
        self.assertEqual(len(self.foundry.list(status="approved")), 0)

    def test_rejects_invalid_brain_and_http_source(self):
        with self.assertRaisesRegex(ValueError, "unknown_brain_assignment"):
            self.register(brains=["unknown"])
        with self.assertRaisesRegex(ValueError, "source_url_must_be_http"):
            self.register(source_url="file:///tmp/package")

    def test_review_requires_auditable_evidence(self):
        item = self.register(artifact=None)
        with self.assertRaisesRegex(ValueError, "reviewer_and_https_evidence_required"):
            self.foundry.review(item["library_id"], decision="approve",
                                reviewer="", evidence_ref="not-a-url", artifact_scope="package")

    def test_review_rejects_unknown_library(self):
        with self.assertRaises(KeyError):
            self.foundry.review("missing", decision="reject",
                                reviewer="reviewer", evidence_ref="https://example.org", artifact_scope="package")


if __name__ == "__main__":
    unittest.main()
