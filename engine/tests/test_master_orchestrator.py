import unittest
from alili_engine.brains import BrainRegistry
from alili_engine.master_orchestrator import ACMasterOrchestrator


class ACMasterOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.master = ACMasterOrchestrator(BrainRegistry())

    def test_multidomain_request_is_split_across_specialists(self):
        plan = self.master.plan("ابحث عن مصادر ثم برمج تطبيقاً واختبره")
        ids = {item["brain_id"] for item in plan["assignments"]}
        self.assertTrue({"ac_research", "ac_code", "ac_execution", "ac_reasoning"} <= ids)
        self.assertEqual(plan["mode"], "independent_specialists_with_central_coordination")
        self.assertFalse(plan["execution"]["dispatched"])
        self.assertTrue(all(item["isolated_context"] for item in plan["assignments"]))

    def test_requested_brains_are_validated_and_included(self):
        plan = self.master.plan("اشرح الموضوع", requested_brains=["ac_science"])
        self.assertIn("ac_science", {item["brain_id"] for item in plan["assignments"]})

    def test_unknown_brain_and_unbounded_capacity_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown_brain"):
            self.master.plan("task", requested_brains=["ac_unknown"])
        with self.assertRaisesRegex(ValueError, "max_brains_out_of_range"):
            self.master.plan("task", max_brains=99)

    def test_default_task_uses_reasoning_without_claiming_runtime(self):
        plan = self.master.plan("فسر هذا المفهوم")
        self.assertEqual([item["brain_id"] for item in plan["assignments"]], ["ac_reasoning"])
        self.assertTrue(all(not item["dispatchable"] for item in plan["assignments"]))
        self.assertFalse(plan["learning"]["automatic_weight_training"])


if __name__ == "__main__":
    unittest.main()
