"""Fail-closed async adapter for the Cloudflare Workers AI binding.

The hosting Worker injects an async callable around env.AI.run(). This module
never uses API keys, external provider URLs, paid fallbacks, or automatic
billing. The default allowlist contains only the model checked against the
Cloudflare free-plan documentation on 2026-11-21.
"""
from __future__ import annotations

import inspect


FREE_MODEL_ALLOWLIST_2026_11_21 = frozenset({
    "@cf/zai-org/glm-4.7-flash",
})


class CloudflareWorkersAIModelClient:
    def __init__(
        self,
        ai_run,
        model_id: str,
        *,
        free_confirmed: bool = False,
        allowed_models=None,
        result_converter=None,
    ):
        self.ai_run = ai_run
        self.model_id = model_id.strip() if isinstance(model_id, str) else ""
        self.free_confirmed = free_confirmed is True
        self.allowed_models = frozenset(
            allowed_models if allowed_models is not None
            else FREE_MODEL_ALLOWLIST_2026_11_21
        )
        self.result_converter = result_converter or self._default_convert

    @staticmethod
    def _default_convert(value):
        converter = getattr(value, "to_py", None)
        if callable(converter):
            return converter()
        return value

    async def status(self) -> dict:
        if not callable(self.ai_run):
            return {"status": "unreachable", "reason": "workers_ai_binding_missing"}
        if not self.free_confirmed:
            return {"status": "blocked", "reason": "free_plan_not_explicitly_confirmed"}
        if self.model_id not in self.allowed_models:
            return {"status": "blocked", "reason": "model_not_in_free_allowlist"}
        return {
            "status": "ready",
            "provider": "cloudflare_workers_ai",
            "model": self.model_id,
            "billing_policy": "free_only_no_paid_fallback",
        }

    async def generate(self, messages, *, temperature=0.2, max_tokens=512):
        readiness = await self.status()
        if readiness["status"] != "ready":
            raise RuntimeError(readiness["reason"])
        if not isinstance(messages, list) or not messages or len(messages) > 40:
            raise ValueError("invalid_messages")
        if isinstance(max_tokens, bool) or not isinstance(max_tokens, int) or not 64 <= max_tokens <= 2048:
            raise ValueError("invalid_max_tokens")
        if isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not 0 <= temperature <= 1:
            raise ValueError("invalid_temperature")

        payload = {
            "messages": messages,
            "temperature": float(temperature),
            "max_tokens": max_tokens,
        }
        result = self.ai_run(self.model_id, payload)
        if not inspect.isawaitable(result):
            raise TypeError("workers_ai_binding_must_be_async")
        result = self.result_converter(await result)
        if not isinstance(result, dict):
            raise RuntimeError("workers_ai_invalid_response")
        content = result.get("response")
        if not isinstance(content, str) or not content.strip():
            choices = result.get("choices")
            if isinstance(choices, list) and choices and isinstance(choices[0], dict):
                message = choices[0].get("message")
                if isinstance(message, dict):
                    content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("workers_ai_empty_response")
        return {
            "model": result.get("model", self.model_id),
            "content": content,
            "usage": result.get("usage"),
            "source": "cloudflare_workers_ai",
        }
