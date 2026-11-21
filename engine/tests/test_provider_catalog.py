import unittest

from alili_engine.provider_catalog import ProviderCatalog


class ProviderCatalogTests(unittest.TestCase):
    def setUp(self):
        self.catalog = ProviderCatalog()

    def test_catalog_is_discovery_only_and_every_provider_is_disabled(self):
        summary = self.catalog.summary()
        self.assertGreater(summary["total"], 0)
        self.assertEqual(summary["connected"], 0)
        self.assertEqual(summary["enabled"], 0)
        self.assertTrue(all(item["enabled_by_default"] is False for item in self.catalog.list(limit=200)))

    def test_unknown_or_unverified_hosted_provider_is_denied(self):
        self.assertFalse(self.catalog.activation_decision("missing-provider")["allowed"])
        decision = self.catalog.activation_decision("kaggle")
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "hosted_provider_not_verified")

    def test_hosted_provider_requires_every_account_specific_check(self):
        evidence = {
            "current_free_terms_verified": True,
            "no_card_requirement_verified": True,
            "billing_disabled_verified": True,
            "quota_guard_verified": True,
            "region_supported_verified": True,
        }
        self.assertTrue(self.catalog.activation_decision("kaggle", evidence)["allowed"])
        evidence["no_card_requirement_verified"] = False
        self.assertFalse(self.catalog.activation_decision("kaggle", evidence)["allowed"])

    def test_card_required_or_billing_linked_provider_is_always_denied(self):
        for provider_id in ("cloudflare_r2", "replicate"):
            with self.subTest(provider_id=provider_id):
                self.assertFalse(self.catalog.activation_decision(provider_id, {
                    "current_free_terms_verified": True,
                    "no_card_requirement_verified": True,
                    "billing_disabled_verified": True,
                    "quota_guard_verified": True,
                    "region_supported_verified": True,
                })["allowed"])

    def test_local_runtime_requires_license_and_runtime_checks(self):
        self.assertFalse(self.catalog.activation_decision("ollama")["allowed"])
        self.assertTrue(self.catalog.activation_decision("ollama", {
            "license_reviewed": True, "runtime_available": True
        })["allowed"])

    def test_filters_and_details(self):
        self.assertTrue(all(item["category"] == "vector_database"
                            for item in self.catalog.list(category="vector_database")))
        self.assertIsNotNone(self.catalog.get("qdrant_cloud"))
        self.assertIsNone(self.catalog.get("not-real"))


if __name__ == "__main__":
    unittest.main()
