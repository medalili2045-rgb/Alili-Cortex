"""Small SQLite task store with explicit state transitions."""

import json
import sqlite3
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class TaskStore:
    _transitions = {
        "queued": {"planning", "failed"},
        "planning": {"planned", "failed"},
        "planned": set(),
        "failed": set(),
    }

    def __init__(self, database_path: str):
        self.database_path = database_path if database_path == ":memory:" else str(Path(database_path).expanduser())
        if self.database_path != ":memory:":
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self):
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_text TEXT NOT NULL,
                    capability_id TEXT,
                    plan_json TEXT,
                    error_code TEXT
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_created_at ON tasks(created_at)")
            db.execute("""
                CREATE TABLE IF NOT EXISTS brain_dispatches (
                    dispatch_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    objective TEXT NOT NULL,
                    plan_json TEXT NOT NULL,
                    result_json TEXT,
                    error_code TEXT
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_brain_dispatches_created_at ON brain_dispatches(created_at)")

    def create_brain_dispatch(self, dispatch_id: str, objective: str, plan: dict,
                              *, status: str = "queued") -> dict:
        if not isinstance(dispatch_id, str) or not dispatch_id.startswith("ac-dispatch-"):
            raise ValueError("invalid_dispatch_id")
        if not isinstance(objective, str) or not objective.strip() or len(objective) > 4000:
            raise ValueError("invalid_dispatch_objective")
        if not isinstance(plan, dict):
            raise ValueError("invalid_dispatch_plan")
        encoded_plan = json.dumps(plan, ensure_ascii=False)
        if len(encoded_plan) > 100_000:
            raise ValueError("dispatch_plan_too_large")
        now = utc_now()
        with closing(self._connect()) as db, db:
            db.execute(
                """INSERT INTO brain_dispatches
                   (dispatch_id, created_at, updated_at, status, objective, plan_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (dispatch_id, now, now, status, objective, encoded_plan),
            )
        return self.get_brain_dispatch(dispatch_id)

    def update_brain_dispatch(self, dispatch_id: str, status: str, *,
                              result: dict | None = None, error_code: str | None = None) -> dict:
        allowed = {"queued", "running", "blocked", "partial_failure",
                   "completed_pending_review", "completed", "failed"}
        if status not in allowed:
            raise ValueError("invalid_dispatch_status")
        encoded = None
        if result is not None:
            encoded = json.dumps(result, ensure_ascii=False)
            if len(encoded) > 200_000:
                raise ValueError("dispatch_result_too_large")
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT dispatch_id FROM brain_dispatches WHERE dispatch_id = ?",
                             (dispatch_id,)).fetchone()
            if row is None:
                raise KeyError(dispatch_id)
            db.execute(
                """UPDATE brain_dispatches SET status = ?, updated_at = ?,
                   result_json = COALESCE(?, result_json), error_code = ?
                   WHERE dispatch_id = ?""",
                (status, utc_now(), encoded, error_code, dispatch_id),
            )
        return self.get_brain_dispatch(dispatch_id)

    def get_brain_dispatch(self, dispatch_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM brain_dispatches WHERE dispatch_id = ?",
                             (dispatch_id,)).fetchone()
        if row is None:
            return None
        return {
            "dispatch_id": row["dispatch_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status"],
            "objective": row["objective"],
            "plan": json.loads(row["plan_json"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error_code": row["error_code"],
        }

    def list_brain_dispatches(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("invalid_dispatch_limit")
        if status is not None and status not in {
            "queued", "running", "blocked", "partial_failure",
            "completed_pending_review", "completed", "failed"
        }:
            raise ValueError("invalid_dispatch_status_filter")
        with closing(self._connect()) as db:
            if status:
                rows = db.execute(
                    "SELECT * FROM brain_dispatches WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                    (status, limit)).fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM brain_dispatches ORDER BY created_at DESC LIMIT ?",
                    (limit,)).fetchall()
        return [self._decode_brain_dispatch(row) for row in rows]

    @staticmethod
    def _decode_brain_dispatch(row) -> dict:
        return {
            "dispatch_id": row["dispatch_id"], "created_at": row["created_at"],
            "updated_at": row["updated_at"], "status": row["status"],
            "objective": row["objective"], "plan": json.loads(row["plan_json"]),
            "result": json.loads(row["result_json"]) if row["result_json"] else None,
            "error_code": row["error_code"],
        }

    def create(self, input_text: str) -> dict:
        task_id = str(uuid.uuid4())
        now = utc_now()
        with closing(self._connect()) as db, db:
            db.execute(
                "INSERT INTO tasks(task_id, created_at, updated_at, status, input_text) VALUES (?, ?, ?, 'queued', ?)",
                (task_id, now, now, input_text),
            )
        return self.get(task_id)

    def transition(self, task_id: str, status: str, *, capability_id=None, plan=None, error_code=None):
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT status FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if status not in self._transitions.get(row["status"], set()):
                raise ValueError(f"Invalid task transition: {row['status']} -> {status}")
            db.execute(
                """UPDATE tasks SET status = ?, updated_at = ?, capability_id = COALESCE(?, capability_id),
                   plan_json = COALESCE(?, plan_json), error_code = ? WHERE task_id = ?""",
                (status, utc_now(), capability_id, json.dumps(plan, ensure_ascii=False) if plan is not None else None, error_code, task_id),
            )
        return self.get(task_id)

    def get(self, task_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            return None
        return self._decode(row)

    @staticmethod
    def _decode(row) -> dict:
        return {
            "task_id": row["task_id"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "status": row["status"],
            "input": row["input_text"],
            "capability_id": row["capability_id"],
            "plan": json.loads(row["plan_json"]) if row["plan_json"] else None,
            "error_code": row["error_code"],
        }
