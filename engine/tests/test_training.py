import os
import tempfile
import unittest

from alili_engine.training import TrainingStore, training_policy


class TrainingCenterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = TrainingStore(os.path.join(self.temp.name, "training.sqlite3"))

    def tearDown(self):
        self.temp.cleanup()

    def test_all_domain_curricula_are_available(self):
        curricula = self.store.curricula()
        self.assertGreaterEqual(len(curricula), 15)
        self.assertEqual({item["learning_mode"] for item in curricula}, {"hybrid"})
        self.assertEqual({item["autonomy"] for item in curricula}, {"sandbox"})

    def test_manual_scheduled_and_continuous_triggers_only_queue(self):
        for trigger in ("manual", "scheduled", "continuous"):
            run = self.store.create_run(curriculum_id="programming", trigger_mode=trigger)
            self.assertEqual(run["status"], "sandbox_queued")
            self.assertEqual(run["execution_status"], "trainer_runtime_not_configured")
            self.assertEqual(run["autonomy"], "sandbox")

    def test_unknown_curriculum_and_invalid_dataset_license_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown_curriculum"):
            self.store.create_run(curriculum_id="not-real")
        with self.assertRaisesRegex(ValueError, "license_id"):
            self.store.create_run(curriculum_id="research",
                dataset_manifest=[{"name": "set", "source": "local"}])

    def test_held_out_evaluation_is_required_and_never_updates_weights(self):
        run = self.store.create_run(curriculum_id="reasoning")
        with self.assertRaisesRegex(ValueError, "held_out"):
            self.store.record_evaluation(run["run_id"], metrics={"accuracy": 0.95}, held_out=False)
        result = self.store.record_evaluation(run["run_id"],
            metrics={"accuracy": 0.95, "reliability": 0.91}, held_out=True)
        self.assertTrue(result["evaluation"]["score_threshold_met"])
        self.assertFalse(result["evaluation"]["passed"])
        self.assertFalse(result["evaluation"]["eligible_for_human_review"])
        self.assertEqual(result["evaluation"]["verification_status"], "self_reported_unverified")
        self.assertFalse(result["evaluation"]["weights_updated"])

    def test_low_score_is_not_eligible_for_review(self):
        run = self.store.create_run(curriculum_id="science")
        result = self.store.record_evaluation(run["run_id"],
            metrics={"accuracy": 0.65}, held_out=True)
        self.assertFalse(result["evaluation"]["score_threshold_met"])
        self.assertFalse(result["evaluation"]["passed"])
        self.assertFalse(result["evaluation"]["eligible_for_human_review"])

    def test_in_memory_database_is_kept_alive_across_connections(self):
        store = TrainingStore(":memory:")
        run = store.create_run(curriculum_id="language")
        self.assertIsNotNone(store.get_run(run["run_id"]))

    def test_policy_is_free_and_sandboxed(self):
        policy = training_policy()
        self.assertEqual(policy["learning_mode"], "hybrid")
        self.assertEqual(policy["autonomy"], "sandbox")
        self.assertEqual(policy["paid_services"], "forbidden")
        self.assertEqual(policy["weight_updates"], "not_performed")


if __name__ == "__main__":
    unittest.main()
