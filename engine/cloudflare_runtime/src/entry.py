"""Alili Cortex Cloudflare Python Worker adapter.

This adapter is deliberately separate from the local threaded engine. It does not
import subprocess/threading/resource-based sandbox code and never invokes Workers AI.
"""
import hmac
import json
import os
from urllib.parse import urlsplit

from workers import Response, WorkerEntrypoint

MAX_BODY_BYTES = 16 * 1024
MAX_EVENT_TYPE = 80
BRAIN_IDS = (
    "reasoning", "code", "science", "research", "vision", "media",
    "language", "strategy", "memory", "execution", "learning_factory",
)


def _json(payload, status=200):
    return Response(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        status=status,
        headers={"content-type": "application/json; charset=utf-8",
                 "cache-control": "no-store",
                 "x-content-type-options": "nosniff"},
    )


class Default(WorkerEntrypoint):
    def _authorized(self, request):
        expected = getattr(self.env, "AC_ENGINE_API_KEY", None)
        supplied = request.headers.get("Authorization", "")
        if not expected or not isinstance(expected, str):
            return False
        prefix = "Bearer "
        return supplied.startswith(prefix) and hmac.compare_digest(
            supplied[len(prefix):], expected
        )

    async def fetch(self, request):
        parsed = urlsplit(request.url)
        path = parsed.path

        if request.method == "GET" and path == "/health":
            return _json({"ok": True, "service": "ac-cortex-python-runtime",
                          "version": "0.1.0", "deployment": "not_assumed"})

        if not self._authorized(request):
            return _json({"ok": False, "error": "unauthorized"}, 401)

        if request.method == "GET" and path == "/v1/status":
            try:
                probe = await self.env.AC_DB.prepare("SELECT 1 AS ok").first()
                d1_ready = bool(probe and probe["ok"] == 1)
            except Exception:
                d1_ready = False
            return _json({
                "ok": True,
                "runtime": "cloudflare_python_worker",
                "version": getattr(self.env, "AC_RUNTIME_VERSION", "0.1.0"),
                "database": {"binding": "AC_DB", "reachable": d1_ready},
                "inference": {"enabled": False, "reason": "explicit_free_quota_and_billing_gate"},
                "execution": {"enabled": False, "reason": "no_os_isolated_runner_in_worker"},
                "paid_fallback": False,
            }, 200 if d1_ready else 503)

        if request.method == "GET" and path == "/v1/brains":
            return _json({"ok": True, "routing_mode": "catalog_only",
                          "execution_enabled": False,
                          "brains": [{"id": brain_id, "status": "registered_not_executing"}
                                     for brain_id in BRAIN_IDS]})

        if request.method == "GET" and path == "/v1/models":
            return _json({"ok": True, "catalog_only": True, "inference_enabled": False,
                          "models": [], "note": "No model is downloaded, trained, or invoked by this adapter."})

        if request.method == "POST" and path == "/v1/inference":
            # Intentionally hard-disabled. A binding alone is not proof of free
            # eligibility, and Workers AI calls can consume billable account usage.
            return _json({"ok": False, "error": "inference_disabled",
                          "reason": "free_account_eligibility_and_enforceable_quota_guard_not_verified",
                          "paid_fallback": False}, 503)

        if request.method == "POST" and path == "/v1/events":
            raw_length = request.headers.get("Content-Length", "")
            try:
                length = int(raw_length)
            except (TypeError, ValueError):
                return _json({"ok": False, "error": "content_length_required"}, 411)
            if length < 1 or length > MAX_BODY_BYTES:
                return _json({"ok": False, "error": "request_too_large_or_empty"}, 413)
            try:
                payload = await request.json()
            except Exception:
                return _json({"ok": False, "error": "invalid_json"}, 400)
            if not isinstance(payload, dict):
                return _json({"ok": False, "error": "invalid_request"}, 400)
            event_type = payload.get("event_type")
            details = payload.get("details", {})
            if (not isinstance(event_type, str) or not event_type.strip()
                    or len(event_type) > MAX_EVENT_TYPE or not isinstance(details, dict)):
                return _json({"ok": False, "error": "invalid_event"}, 400)
            try:
                await self.env.AC_DB.prepare(
                    "INSERT INTO ac_runtime_events (event_type, details_json, created_at) "
                    "VALUES (?, ?, CURRENT_TIMESTAMP)"
                ).bind(event_type.strip(), json.dumps(details, ensure_ascii=False)).run()
            except Exception:
                return _json({"ok": False, "error": "database_write_unavailable",
                              "hint": "Apply the reviewed additive D1 migration first."}, 503)
            return _json({"ok": True, "stored": True}, 201)

        return _json({"ok": False, "error": "not_found"}, 404)
