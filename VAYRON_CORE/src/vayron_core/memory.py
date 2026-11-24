"""Small local SQLite memory store; no network access."""

import sqlite3
from pathlib import Path
from datetime import datetime, timezone


class MemoryStore:
    def __init__(self, database_path: str | Path = "data/vayron_memory.sqlite3") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT 'general',
                    created_at TEXT NOT NULL
                )
            """)

    def add(self, content: str, category: str = "general") -> int:
        value = content.strip()
        if not value:
            raise ValueError("Memory content cannot be empty")
        with self._connect() as db:
            cursor = db.execute(
                "INSERT INTO memories(content, category, created_at) VALUES (?, ?, ?)",
                (value, category.strip() or "general", datetime.now(timezone.utc).isoformat()),
            )
            return int(cursor.lastrowid)

    def search(self, query: str, limit: int = 20) -> list[dict[str, object]]:
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500")
        term = f"%{query.strip()}%"
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, content, category, created_at FROM memories "
                "WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (term, limit),
            ).fetchall()
        return [
            {"id": row[0], "content": row[1], "category": row[2], "created_at": row[3]}
            for row in rows
        ]
