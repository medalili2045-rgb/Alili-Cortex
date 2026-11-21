import os
import tempfile
import unittest

from alili_engine.brains import BrainRegistry
from alili_engine.brain_runtime import ACBrianRuntime, BrainDispatchError
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class FakeLocalModel:
    def __init__(self, ready=True, fail_brain=None, review_response="Verdict: ACCEPT. No blocking contradictions found."):
        self.ready = ready
        self.fail_brain = fail_brain
        self.review_response = review_response
        self.calls = []

    def status(self):
        return {"status": "ready" if self.ready else "unreachable",
                "kind": "local_loopback", "fallback": "disabled"}

    def generate(self, messages, **kwargs):
        self.calls.append(messages)
        system = messages[0]["content"]
        if self.fail_brain and self.fail_brain in system:
            raise RuntimeError("simulated_local_failure")
        if "independent quality reviewer" in system:
            content = self.review_response
        else:
            content = "Specialist findings with assumptions and risks."
        return {"model": "test-local-model", "content": content,
                "usage": {"total_tokens": 12}, "source": "local"}


def sample_plan():
    return {
        "plan_id": "plan-test",
        "objective": "Design and test a small software service",
        "assignments": [
            {"brain_id": "ac_code", "objective": "Design the service"},
            {"brain_id": "ac_reasoning", "objective": "Review assumptions"},
        ],
    }


class BrainRuntimeTests(unittest.TestCase):
    def test_unconfigured_runtime_fails_closed_without_model_calls(self):
        model = FakeLocalModel(ready=False)
        runtime = ACBrianRuntime(model, BrainRegistry())
        result = runtime.dispatch(sample_plan())
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["dispatched"])
        self.assertEqual(model.calls, [])
        self.assertEqual(result["hosted_fallback"], "disabled")

    def test_local_dispatch_runs_isolated_specialists_and_quality_review(self):
        model = FakeLocalModel()
        runtime = ACBrianRuntime(model, BrainRegistry(), max_workers=2)
        result = runtime.dispatch(sample_plan())
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["dispatched"])
        self.assertTrue(result["finalized"])
        self.assertEqual(result["quality_review"]["verdict"], "accepted")
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(item["isolated_context"] for item in result["results"]))
        self.assertEqual(len(model.calls), 3)

    def test_needs_revision_quality_verdict_does_not_finalize(self):
        model = FakeLocalModel(review_response="Verdict: NEEDS_REVISION. Evidence is missing.")
        runtime = ACBrianRuntime(model, BrainRegistry())
        result = runtime.dispatch(sample_plan())
        self.assertEqual(result["status"], "completed_pending_review")
        self.assertFalse(result["finalized"])
        self.assertEqual(result["quality_review"]["verdict"], "needs_revision")

    def test_unregistered_brain_is_rejected_before_dispatch(self):
        runtime = ACBrianRuntime(FakeLocalModel(), BrainRegistry())
        plan = sample_plan()
        plan["assignments"][0]["brain_id"] = "ac_unknown"
        with self.assertRaises(BrainDispatchError):
            runtime.dispatch(plan)

    def test_specialist_failure_prevents_finalization(self):
        model = FakeLocalModel(fail_brain="software engineering specialist")
        runtime = ACBrianRuntime(model, BrainRegistry())
        result = runtime.dispatch(sample_plan())
        self.assertEqual(result["status"], "partial_failure")
        self.assertFalse(result["finalized"])
        self.assertEqual(result["quality_review"]["status"], "not_run")

    def test_engine_service_wires_local_dispatch_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            model = FakeLocalModel()
            service = EngineService(
                TaskStore(os.path.join(directory, "runtime.sqlite3")),
                model_client=model,
            )
            plan = service.plan_brains("Design and test a software API")
            result = service.dispatch_brains(plan)
            saved = service.get_brain_dispatch(result["dispatch_id"])
            listed = service.list_brain_dispatches(limit=5)
        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["finalized"])
        self.assertEqual(saved["status"], "completed")
        self.assertEqual(saved["result"]["dispatch_id"], result["dispatch_id"])
        self.assertTrue(any(item["dispatch_id"] == result["dispatch_id"] for item in listed))

    def test_duplicate_assignments_are_rejected(self):
        runtime = ACBrianRuntime(FakeLocalModel(), BrainRegistry())
        plan = sample_plan()
        plan["assignments"].append(plan["assignments"][0])
        with self.assertRaises(BrainDispatchError):
            runtime.dispatch(plan)


if __name__ == "__main__":
    unittest.main()
