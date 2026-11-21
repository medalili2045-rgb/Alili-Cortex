import unittest

from alili_engine.study_blueprints import list_blueprints


class ACStudyBlueprintTests(unittest.TestCase):
    def test_blueprints_cover_specialist_brains(self):
        for brain_id in ("ac_reasoning", "ac_code", "ac_research", "ac_science",
                         "ac_vision", "ac_media", "ac_language", "ac_strategy",
                         "ac_execution", "ac_memory"):
            self.assertTrue(list_blueprints(brain_id=brain_id), brain_id)

    def test_each_blueprint_has_sources_lessons_and_deliverables(self):
        items = list_blueprints()
        self.assertGreaterEqual(len(items), 12)
        for item in items:
            self.assertTrue(item["source_ids"])
            self.assertTrue(item["lessons"])
            for lesson in item["lessons"]:
                self.assertTrue(lesson["objective"])
                self.assertTrue(lesson["study_actions"])
                self.assertTrue(lesson["deliverable"])
            self.assertEqual(item["status"], "study_plan_only_not_ingested")

    def test_external_reference_blueprints_are_distinct(self):
        memory = list_blueprints(domain="retrieval_and_memory")
        execution = list_blueprints(domain="software")
        memory_item = next(item for item in memory if item["blueprint_id"] == "persistent_agent_memory")
        execution_item = next(item for item in execution if item["blueprint_id"] == "software_execution_agents")
        self.assertEqual(memory_item["source_ids"], ["letta_code"])
        self.assertEqual(execution_item["source_ids"], ["openhands_core"])
        self.assertNotEqual(memory_item["brain_ids"], execution_item["brain_ids"])
        self.assertEqual(memory_item["status"], "study_plan_only_not_ingested")

    def test_brain_filter_does_not_mutate_catalog(self):
        first = list_blueprints(brain_id="ac_code")
        first[0]["source_ids"].clear()
        self.assertTrue(list_blueprints(brain_id="ac_code")[0]["source_ids"])

    def test_invalid_filters_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_brain_id"):
            list_blueprints(brain_id=" ")
        with self.assertRaisesRegex(ValueError, "invalid_domain"):
            list_blueprints(domain=" ")


if __name__ == "__main__":
    unittest.main()
