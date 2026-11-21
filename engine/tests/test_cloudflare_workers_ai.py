import unittest

from alili_engine.cloudflare_workers_ai import (
    CloudflareWorkersAIModelClient,
    FREE_MODEL_ALLOWLIST_2026_11_21,
)


class FakeAIRun:
    def __init__(self, response=None):
        self.response = response or {
            "response": "A grounded answer.",
            "model": "@cf/zai-org/glm-4.7-flash",
            "usage": {"prompt_tokens": 10, "completion_tokens": 8},
        }
        self.calls = []

    async def __call__(self, model_id, payload):
        self.calls.append((model_id, payload))
        return self.response


class CloudflareWorkersAIClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_free_allowlisted_model_is_ready(self):
        ai = FakeAIRun()
        client = CloudflareWorkersAIModelClient(
            ai, "@cf/zai-org/glm-4.7-flash", free_confirmed=True
        )
        status = await client.status()
        self.assertEqual(status["status"], "ready")
        self.assertEqual(status["billing_policy"], "free_only_no_paid_fallback")

    async def test_unconfirmed_free_plan_fails_closed(self):
        ai = FakeAIRun()
        client = CloudflareWorkersAIModelClient(
            ai, "@cf/zai-org/glm-4.7-flash", free_confirmed=False
        )
        self.assertEqual((await client.status())["status"], "blocked")
        with self.assertRaisesRegex(RuntimeError, "free_plan_not_explicitly_confirmed"):
            await client.generate([{"role": "user", "content": "hello"}])
        self.assertEqual(ai.calls, [])

    async def test_model_outside_free_allowlist_is_rejected(self):
        ai = FakeAIRun()
        client = CloudflareWorkersAIModelClient(
            ai, "@cf/example/paid-model", free_confirmed=True
        )
        self.assertEqual((await client.status())["reason"], "model_not_in_free_allowlist")
        with self.assertRaisesRegex(RuntimeError, "model_not_in_free_allowlist"):
            await client.generate([{"role": "user", "content": "hello"}])
        self.assertEqual(ai.calls, [])

    async def test_generation_uses_binding_and_returns_normalized_result(self):
        ai = FakeAIRun()
        client = CloudflareWorkersAIModelClient(
            ai, "@cf/zai-org/glm-4.7-flash", free_confirmed=True
        )
        result = await client.generate(
            [{"role": "user", "content": "hello"}],
            temperature=0.3,
            max_tokens=256,
        )
        self.assertEqual(result["content"], "A grounded answer.")
        self.assertEqual(result["source"], "cloudflare_workers_ai")
        self.assertEqual(len(ai.calls), 1)
        self.assertEqual(ai.calls[0][0], "@cf/zai-org/glm-4.7-flash")
        self.assertEqual(ai.calls[0][1]["max_tokens"], 256)

    async def test_empty_response_is_rejected(self):
        ai = FakeAIRun(response={"response": ""})
        client = CloudflareWorkersAIModelClient(
            ai, "@cf/zai-org/glm-4.7-flash", free_confirmed=True
        )
        with self.assertRaisesRegex(RuntimeError, "workers_ai_empty_response"):
            await client.generate([{"role": "user", "content": "hello"}])

    async def test_allowlist_is_explicit_and_nonempty(self):
        self.assertIn("@cf/zai-org/glm-4.7-flash", FREE_MODEL_ALLOWLIST_2026_11_21)
        self.assertEqual(len(FREE_MODEL_ALLOWLIST_2026_11_21), 1)


if __name__ == "__main__":
    unittest.main()
