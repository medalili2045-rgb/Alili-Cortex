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
