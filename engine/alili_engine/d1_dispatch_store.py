"""Async D1 persistence adapter for AC brain dispatch history.

Implements the dispatch-store methods used by the engine without local SQLite,
threads, filesystem access, or synchronous database calls.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone


_ALLOWED_STATUSES = {
    "queued", "running", "blocked", "partial_failure",
    "completed_pending_review", "completed", "failed",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode(row):
    if row is None:
        return None
    return {
        "dispatch_id": row["dispatch_id"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "status": row["status"],
        "objective": row["objective"],
        "plan": json.loads(row["plan_json"]),
        "result": json.loads(row["result_json"]) if row.get("result_json") else None,
        "error_code": row.get("error_code"),
    }


class D1BrainDispatchStore:
    """D1-backed async equivalent of TaskStore brain-dispatch persistence."""

    def __init__(self, database):
        if database is None:
            raise ValueError("d1_binding_required")
        self.database = database

    async def _first(self, sql: str, *values):
        statement = self.database.prepare(sql)
        if values:
            statement = statement.bind(*values)
        row = await statement.first()
        return row.to_py() if callable(getattr(row, "to_py", None)) else row

    async def _all(self, sql: str, *values):
        statement = self.database.prepare(sql)
        if values:
            statement = statement.bind(*values)
        result = await statement.all()
        result = result.to_py() if callable(getattr(result, "to_py", None)) else result
        if not isinstance(result, dict):
            raise RuntimeError("d1_invalid_result")
        rows = result.get("results", [])
        return [row.to_py() if callable(getattr(row, "to_py", None)) else row for row in rows]

    async def _run(self, sql: str, *values):
        statement = self.database.prepare(sql)
        if values:
            statement = statement.bind(*values)
        return await statement.run()

    async def create_brain_dispatch(self, dispatch_id: str, objective: str,
                                    plan: dict, *, status: str = "queued") -> dict:
        if not isinstance(dispatch_id, str) or not dispatch_id.startswith("ac-dispatch-"):
            raise ValueError("invalid_dispatch_id")
        if not isinstance(objective, str) or not objective.strip() or len(objective) > 4000:
            raise ValueError("invalid_dispatch_objective")
        if not isinstance(plan, dict):
            raise ValueError("invalid_dispatch_plan")
        if status not in _ALLOWED_STATUSES:
            raise ValueError("invalid_dispatch_status")
        encoded = json.dumps(plan, ensure_ascii=False, separators=(",", ":"))
        if len(encoded) > 100_000:
            raise ValueError("dispatch_plan_too_large")
        now = _now()
        await self._run(
            """INSERT INTO ac_brain_dispatches
               (dispatch_id, created_at, updated_at, status, objective, plan_json)
               VALUES (?, ?, ?, ?, ?, ?)""",
            dispatch_id, now, now, status, objective, encoded,
        )
        return await self.get_brain_dispatch(dispatch_id)

    async def update_brain_dispatch(self, dispatch_id: str, status: str, *,
                                    result: dict | None = None,
                                    error_code: str | None = None) -> dict:
        if status not in _ALLOWED_STATUSES:
            raise ValueError("invalid_dispatch_status")
        encoded = None
        if result is not None:
            encoded = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            if len(encoded) > 200_000:
                raise ValueError("dispatch_result_too_large")
        existing = await self.get_brain_dispatch(dispatch_id)
        if existing is None:
            raise KeyError(dispatch_id)
        await self._run(
            """UPDATE ac_brain_dispatches
               SET status = ?, updated_at = ?,
                   result_json = COALESCE(?, result_json), error_code = ?
               WHERE dispatch_id = ?""",
            status, _now(), encoded, error_code, dispatch_id,
        )
        return await self.get_brain_dispatch(dispatch_id)

    async def get_brain_dispatch(self, dispatch_id: str) -> dict | None:
        row = await self._first(
            """SELECT dispatch_id, created_at, updated_at, status, objective,
                      plan_json, result_json, error_code
               FROM ac_brain_dispatches WHERE dispatch_id = ?""",
            dispatch_id,
        )
        return _decode(row)

    async def list_brain_dispatches(self, *, status: str | None = None,
                                    limit: int = 50) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("invalid_dispatch_limit")
        if status is not None and status not in _ALLOWED_STATUSES:
            raise ValueError("invalid_dispatch_status_filter")
        columns = """dispatch_id, created_at, updated_at, status, objective,
                     plan_json, result_json, error_code"""
        if status is None:
            rows = await self._all(
                f"SELECT {columns} FROM ac_brain_dispatches ORDER BY created_at DESC LIMIT ?",
                limit,
            )
        else:
            rows = await self._all(
                f"SELECT {columns} FROM ac_brain_dispatches WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                status, limit,
            )
        return [_decode(row) for row in rows]
