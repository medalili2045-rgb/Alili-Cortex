"""Cloudflare Python Worker entrypoint for the Alili Cortex engine preview.

This Worker is intentionally separate from the live alili-cortex gateway.
It uses only Workers AI + D1 bindings and fails closed unless the account's
free-plan eligibility is explicitly confirmed through a deployment variable.
"""
from __future__ import annotations

import hmac
import json
import os
from urllib.parse import parse_qs, urlsplit

from workers import Response, WorkerEntrypoint

from alili_engine.async_brain_runtime import ACAsyncBrainRuntime
from alili_engine.brains import BrainRegistry
from alili_engine.cloudflare_workers_ai import CloudflareWorkersAIModelClient
from alili_engine.d1_dispatch_store import D1BrainDispatchStore
from alili_engine.master_orchestrator import ACMasterOrchestrator


MAX_BODY_BYTES = 128 * 1024
MODEL_DEFAULT = "@cf/zai-org/glm-4.7-flash"


def _plain(value):
    converter = getattr(value, "to_py", None)
    return converter() if callable(converter) else value


class Default(WorkerEntrypoint):
    def _engine(self):
        env = self.env
        token = getattr(env, "ALILI_ENGINE_API_TOKEN", None)
        model_id = getattr(env, "ALILI_WORKERS_AI_MODEL", MODEL_DEFAULT)
        free_confirmed = str(getattr(env, "ALILI_FREE_PLAN_CONFIRMED", "false")).lower() == "true"

        ai_binding = getattr(env, "AI", None)
        ai_run = getattr(ai_binding, "run", None) if ai_binding is not None else None
        model = CloudflareWorkersAIModelClient(
            ai_run,
            model_id,
            free_confirmed=free_confirmed,
        )
        registry = BrainRegistry()
        runtime = ACAsyncBrainRuntime(model, registry, max_workers=3)
        store = D1BrainDispatchStore(getattr(env, "AC_STATE", None))
        master = ACMasterOrchestrator(registry)
        return token, registry, runtime, store, master

    def _authorized(self, request, expected_token):
        if not isinstance(expected_token, str) or len(expected_token) < 32:
            return False
        supplied = request.headers.get("Authorization", "")
        if not isinstance(supplied, str) or not supplied.startswith("Bearer "):
            return False
        return hmac.compare_digest(supplied[7:], expected_token)

    def _json(self, status, payload):
        return Response.json(
            payload,
            status=status,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    async def fetch(self, request):
        parsed = urlsplit(request.url)
        path = parsed.path
        if path == "/health" and request.method == "GET":
            try:
                _token, _registry, runtime, _store, _master = self._engine()
                state = await runtime.status()
            except Exception:
                state = {"status": "unavailable"}
            return self._json(200, {
                "ok": True,
                "service": "alili-cortex-python-engine",
                "deployment": "preview",
                "runtime": state,
                "persistence": "d1_binding_required",
                "paid_fallback": "disabled",
            })

        try:
            token, registry, runtime, store, master = self._engine()
        except Exception:
            return self._json(503, {"ok": False, "error": "engine_configuration_unavailable"})
        if not self._authorized(request, token):
            return self._json(401, {"ok": False, "error": "unauthorized"})

        if request.method == "GET" and path == "/v1/brains/runtime":
            return self._json(200, {
                "ok": True,
                "coordinator": "AC Master",
                "brains": registry.all(),
                "runtime": await runtime.status(),
                "execution_tools": "disabled",
                "paid_fallback": "disabled",
            })

        if request.method == "POST" and path == "/v1/brains/plan":
            body, error = await self._read_body(request)
            if error:
                return self._json(error[0], {"ok": False, "error": error[1]})
            try:
                plan = master.plan(
                    body.get("objective"),
                    requested_brains=body.get("requested_brains"),
                    max_brains=body.get("max_brains", 6),
                )
            except (ValueError, TypeError) as exc:
                return self._json(400, {"ok": False, "error": str(exc)})
            return self._json(200, {"ok": True, "plan": plan})

        if request.method == "POST" and path == "/v1/brains/dispatch":
            body, error = await self._read_body(request)
            if error:
                return self._json(error[0], {"ok": False, "error": error[1]})
            plan = body.get("plan")
            if not isinstance(plan, dict):
                return self._json(400, {"ok": False, "error": "plan_required"})
            try:
                dispatch_id = "ac-dispatch-" + os.urandom(10).hex()
                await store.create_brain_dispatch(
                    dispatch_id, plan.get("objective"), plan, status="queued"
                )
                await store.update_brain_dispatch(dispatch_id, "running")
                result = await runtime.dispatch(
                    plan,
                    temperature=body.get("temperature", 0.2),
                    max_tokens=body.get("max_tokens", 512),
                    dispatch_id=dispatch_id,
                )
                record = await store.update_brain_dispatch(
                    dispatch_id,
                    result["status"],
                    result=result,
                    error_code=result.get("reason"),
                )
            except (ValueError, TypeError) as exc:
                return self._json(400, {"ok": False, "error": str(exc)})
            except Exception as exc:
                return self._json(500, {
                    "ok": False,
                    "error": "dispatch_failed",
                    "error_type": type(exc).__name__,
                })
            status = 200 if result.get("finalized") else 202
            return self._json(status, {"ok": True, "result": result, "record": record})

        if request.method == "GET" and path == "/v1/brains/dispatches":
            query = parse_qs(parsed.query)
            try:
                limit = int(query.get("limit", ["50"])[0])
                status_filter = query.get("status", [None])[0]
                items = await store.list_brain_dispatches(status=status_filter, limit=limit)
            except (ValueError, TypeError) as exc:
                return self._json(400, {"ok": False, "error": str(exc)})
            return self._json(200, {"ok": True, "dispatches": items})

        if request.method == "GET" and path.startswith("/v1/brains/dispatches/"):
            dispatch_id = path.removeprefix("/v1/brains/dispatches/")
            if not dispatch_id or "/" in dispatch_id:
                return self._json(404, {"ok": False, "error": "not_found"})
            item = await store.get_brain_dispatch(dispatch_id)
            return self._json(200, {"ok": True, "dispatch": item}) if item else self._json(
                404, {"ok": False, "error": "dispatch_not_found"}
            )

        return self._json(404, {"ok": False, "error": "not_found"})

    async def _read_body(self, request):
        length = request.headers.get("Content-Length")
        if length is not None:
            try:
                if int(length) < 0 or int(length) > MAX_BODY_BYTES:
                    return None, (413, "request_too_large")
            except ValueError:
                return None, (400, "invalid_content_length")
        try:
            body = _plain(await request.json())
        except Exception:
            return None, (400, "invalid_json")
        if not isinstance(body, dict):
            return None, (400, "invalid_request")
        if len(json.dumps(body, ensure_ascii=False)) > MAX_BODY_BYTES:
            return None, (413, "request_too_large")
        return body, None
