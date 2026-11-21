import asyncio
import unittest

from alili_engine.async_brain_runtime import ACAsyncBrainRuntime
from alili_engine.brains import BrainRegistry


def sample_plan():
    return {
        "plan_id": "async-plan-test",
        "objective": "Design and review a small software service",
        "assignments": [
            {"brain_id": "ac_code", "objective": "Design the service"},
            {"brain_id": "ac_reasoning", "objective": "Review assumptions"},
        ],
    }


class FakeAsyncModel:
    def __init__(self, *, ready=True, fail_text=None, review="Verdict: ACCEPT. No blocking issues."):
        self.ready = ready
        self.fail_text = fail_text
        self.review = review
        self.calls = []
        self.active = 0
        self.max_active = 0

    async def status(self):
        return {"status": "ready" if self.ready else "unreachable"}

    async def generate(self, messages, **kwargs):
        self.calls.append(messages)
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            await asyncio.sleep(0.001)
            system = messages[0]["content"]
            if self.fail_text and self.fail_text in system:
                raise RuntimeError("simulated_async_failure")
            if "independent quality reviewer" in system:
                content = self.review
            else:
                content = "Specialist findings with assumptions and risks."
            return {
                "model": "test-async-model",
                "content": content,
                "usage": {"total_tokens": 10},
            }
        finally:
            self.active -= 1


class AsyncBrainRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_dispatches_specialists_and_requires_quality_acceptance(self):
        model = FakeAsyncModel()
        runtime = ACAsyncBrainRuntime(model, BrainRegistry(), max_workers=2)
        result = await runtime.dispatch(sample_plan())

        self.assertEqual(result["status"], "completed")
        self.assertTrue(result["dispatched"])
        self.assertTrue(result["finalized"])
        self.assertEqual(result["quality_review"]["verdict"], "accepted")
        self.assertEqual(len(result["results"]), 2)
        self.assertTrue(all(item["isolated_context"] for item in result["results"]))
        self.assertEqual(len(model.calls), 3)

    async def test_unready_model_blocks_without_dispatch(self):
        model = FakeAsyncModel(ready=False)
        runtime = ACAsyncBrainRuntime(model, BrainRegistry())
        result = await runtime.dispatch(sample_plan())

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["dispatched"])
        self.assertEqual(model.calls, [])

    async def test_needs_revision_does_not_finalize(self):
        model = FakeAsyncModel(review="Verdict: NEEDS_REVISION. Evidence is missing.")
        runtime = ACAsyncBrainRuntime(model, BrainRegistry())
        result = await runtime.dispatch(sample_plan())

        self.assertEqual(result["status"], "completed_pending_review")
        self.assertFalse(result["finalized"])
        self.assertEqual(result["quality_review"]["verdict"], "needs_revision")

    async def test_specialist_failure_prevents_quality_finalization(self):
        model = FakeAsyncModel(fail_text="software engineering specialist")
        runtime = ACAsyncBrainRuntime(model, BrainRegistry())
        result = await runtime.dispatch(sample_plan())

        self.assertEqual(result["status"], "partial_failure")
        self.assertFalse(result["finalized"])
        self.assertEqual(result["quality_review"]["status"], "not_run")

    async def test_concurrency_is_bounded_without_threads(self):
        model = FakeAsyncModel()
        runtime = ACAsyncBrainRuntime(model, BrainRegistry(), max_workers=1)
        result = await runtime.dispatch(sample_plan())

        self.assertEqual(result["status"], "completed")
        self.assertEqual(model.max_active, 1)

    async def test_duplicate_and_unregistered_brains_are_rejected(self):
        runtime = ACAsyncBrainRuntime(FakeAsyncModel(), BrainRegistry())
        plan = sample_plan()
        plan["assignments"].append(plan["assignments"][0])
        with self.assertRaisesRegex(ValueError, "duplicate_or_invalid_brain_id"):
            await runtime.dispatch(plan)

        plan = sample_plan()
        plan["assignments"][0]["brain_id"] = "ac_missing"
        with self.assertRaisesRegex(ValueError, "unregistered_brain"):
            await runtime.dispatch(plan)

    async def test_invalid_sync_model_client_fails_closed(self):
        class SyncClient:
            def status(self):
                return {"status": "ready"}

        runtime = ACAsyncBrainRuntime(SyncClient(), BrainRegistry())
        result = await runtime.dispatch(sample_plan())

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["dispatched"])


if __name__ == "__main__":
    unittest.main()
