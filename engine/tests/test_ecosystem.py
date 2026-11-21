import unittest

from alili_engine.ecosystem import EcosystemRegistry, DOMAINS


class ACEcosystemRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = EcosystemRegistry()

    def test_catalog_contains_broad_domain_coverage(self):
        summary = self.registry.summary()
        self.assertGreaterEqual(summary["source_count"], 40)
        for domain in ("language", "code", "math", "medicine", "robotics", "cad", "audio", "vision"):
            self.assertIn(domain, summary["domains"])

    def test_global_catalog_expands_specialist_ecosystem_coverage(self):
        summary = self.registry.summary()
        self.assertGreaterEqual(summary["source_count"], 75)
        expected = (
            "unsloth", "llama_factory", "deepspeed", "cognee", "graphiti",
            "ragflow", "comfyui", "ffmpeg", "piper_tts", "sherpa_onnx",
            "n8n", "playwright", "temporal", "langgraph", "crewai",
            "goose", "browser_use", "jupyter", "duckdb", "polars",
            "sagemath", "astropy", "openbabel", "openscad", "krita",
        )
        for source_id in expected:
            source = self.registry.get(source_id)
            self.assertIsNotNone(source, source_id)
            self.assertEqual(source["adoption_status"], "catalog_only_not_ingested")
            self.assertTrue(source["license_policy"])
            self.assertTrue(source["study_focus"])

    def test_source_kinds_are_not_mislabeled_as_installed_dependencies(self):
        self.assertEqual(self.registry.get("comfyui")["source_kind"], "media_application")
        self.assertEqual(self.registry.get("duckdb")["source_kind"], "analytical_database")
        self.assertEqual(self.registry.get("langgraph")["source_kind"], "agent_framework")
        self.assertIn("not_assumed_osi_open_source", self.registry.get("n8n")["license_policy"])

    def test_domain_filter_returns_only_matching_sources(self):
        results = self.registry.list(domain="robotics")
        self.assertTrue(results)
        self.assertTrue(all("robotics" in item["domains"] for item in results))

    def test_search_and_limit_are_applied(self):
        results = self.registry.list(query="vector", limit=1)
        self.assertEqual(len(results), 1)
        self.assertIn("vector", " ".join(results[0]["study_focus"]).lower())

    def test_unknown_domain_and_bad_limit_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown_ecosystem_domain"):
            self.registry.list(domain="made_up")
        for limit in (0, 501, True, "10"):
            with self.assertRaisesRegex(ValueError, "limit_must_be_between"):
                self.registry.list(limit=limit)

    def test_license_and_execution_safety_policy_is_explicit(self):
        policy = self.registry.policy()
        self.assertFalse(policy["automatic_install"])
        self.assertFalse(policy["automatic_code_execution"])
        self.assertEqual(policy["paid_services"], "prohibited")
        self.assertEqual(policy["knowledge_quality"]["unknown_license_action"], "quarantine")
        self.assertEqual(policy["current_ingestion_status"], "catalog_only_no_external_content_ingested")

    def test_reference_agent_sources_are_separate_and_license_gated(self):
        letta = self.registry.get("letta_code")
        openhands = self.registry.get("openhands_core")
        self.assertEqual(letta["license_policy"].split(";")[0], "Apache-2.0-code")
        self.assertIn("MIT", openhands["license_policy"])
        self.assertIn("sandboxed execution", " ".join(openhands["study_focus"]))

    def test_every_entry_has_provenance_and_license_gate(self):
        for item in self.registry.list(limit=500):
            self.assertTrue(item["url"].startswith("https://"))
            self.assertTrue(item["license_policy"])
            self.assertTrue(item["study_focus"])


if __name__ == "__main__":
    unittest.main()
