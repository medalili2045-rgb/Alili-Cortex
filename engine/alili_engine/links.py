"""Persistent, typed provenance links across AC source, study and brain records."""
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from .store import utc_now


_ALLOWED = {
    ("source", "evidence"): {"documents"},
    ("evidence", "session"): {"studied_in"},
    ("session", "knowledge"): {"proposes"},
    ("knowledge", "brain"): {"assigned_to"},
    ("evidence", "knowledge"): {"supports"},
    ("evidence", "evidence"): {"compares_with", "corroborates"},
    ("source", "source"): {"related_to"},
    ("knowledge", "knowledge"): {"related_to"},
}


class KnowledgeLinkGraph:
    """Stores explicit relationships without merging node data or brain weights."""

    def __init__(self, database_path):
        self._uri = database_path == ":memory:"
        self.database_path = (f"file:ac_links_{uuid.uuid4().hex}?mode=memory&cache=shared"
                              if self._uri else str(Path(database_path).expanduser()))
        self._keeper = self._connect() if self._uri else None
        if not self._uri:
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS knowledge_links (
                link_id TEXT PRIMARY KEY, source_type TEXT NOT NULL, source_id TEXT NOT NULL,
                relation TEXT NOT NULL, target_type TEXT NOT NULL, target_id TEXT NOT NULL,
                metadata_json TEXT NOT NULL, created_at TEXT NOT NULL,
                UNIQUE(source_type, source_id, relation, target_type, target_id)
            )""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_links_source ON knowledge_links(source_type, source_id)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_links_target ON knowledge_links(target_type, target_id)")

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10, uri=self._uri)
        db.row_factory = sqlite3.Row
        return db

    def add(self, *, source_type, source_id, relation, target_type, target_id, metadata=None, connection=None):
        allowed = _ALLOWED.get((source_type, target_type), set())
        if relation not in allowed:
            raise ValueError("invalid_link_relation_for_node_types")
        if not isinstance(source_id, str) or not source_id or len(source_id) > 200:
            raise ValueError("invalid_link_source_id")
        if not isinstance(target_id, str) or not target_id or len(target_id) > 200:
            raise ValueError("invalid_link_target_id")
        if metadata is None:
            metadata = {}
        if not isinstance(metadata, dict) or len(json.dumps(metadata, ensure_ascii=False)) > 4000:
            raise ValueError("invalid_link_metadata")
        def insert(db):
            row = db.execute("""SELECT * FROM knowledge_links WHERE source_type=? AND source_id=?
                AND relation=? AND target_type=? AND target_id=?""",
                (source_type, source_id, relation, target_type, target_id)).fetchone()
            if row:
                return self._decode(row)
            link_id = str(uuid.uuid4())
            db.execute("""INSERT INTO knowledge_links VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                       (link_id, source_type, source_id, relation, target_type, target_id,
                        json.dumps(metadata, ensure_ascii=False, sort_keys=True), utc_now()))
            row = db.execute("SELECT * FROM knowledge_links WHERE link_id=?", (link_id,)).fetchone()
            return self._decode(row)
        if connection is not None:
            return insert(connection)
        with closing(self._connect()) as db, db:
            return insert(db)

    def list(self, *, node_type=None, node_id=None, limit=100):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 500:
            raise ValueError("link_limit_must_be_between_1_and_500")
        if (node_type is None) != (node_id is None):
            raise ValueError("node_type_and_node_id_must_be_supplied_together")
        with closing(self._connect()) as db:
            if node_type:
                rows = db.execute("""SELECT * FROM knowledge_links
                    WHERE (source_type=? AND source_id=?) OR (target_type=? AND target_id=?)
                    ORDER BY created_at DESC LIMIT ?""",
                    (node_type, node_id, node_type, node_id, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM knowledge_links ORDER BY created_at DESC LIMIT ?",
                                   (limit,)).fetchall()
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row):
        item = dict(row)
        item["metadata"] = json.loads(item.pop("metadata_json"))
        return item
