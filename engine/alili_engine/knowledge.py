"""SQLite-backed, provenance-aware knowledge exchange between AC brains."""

import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from .store import utc_now


class KnowledgeStore:
    """Stores versioned artifacts; publication requires validation and approval."""

    _transitions = {
        "proposed": {"quarantined", "rejected"},
        "quarantined": {"validated", "rejected"},
        "validated": {"approved", "rejected"},
        "approved": {"published", "rejected"},
        "published": {"superseded", "rejected"},
        "rejected": set(),
        "superseded": set(),
    }

    def __init__(self, database_path: str, source_validator=None):
        self.source_validator = source_validator
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
                CREATE TABLE IF NOT EXISTS knowledge_artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    artifact_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    origin_brain TEXT NOT NULL,
                    origin_version TEXT NOT NULL,
                    sources_json TEXT NOT NULL,
                    license_id TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge_artifacts(status)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_created ON knowledge_artifacts(created_at)")

    def propose(self, *, artifact_type: str, title: str, content: str,
                origin_brain: str, origin_version: str, sources: list[str],
                license_id: str, confidence: float = 0.5, metadata: dict | None = None,
                connection=None) -> dict:
        fields = (artifact_type, title, content, origin_brain, origin_version, license_id)
        if any(not isinstance(value, str) or not value.strip() for value in fields):
            raise ValueError("artifact_type, title, content, origin_brain, origin_version and license_id are required")
        if not isinstance(sources, list) or any(not isinstance(item, str) or not item.strip() for item in sources):
            raise ValueError("sources must be a list of non-empty strings")
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if metadata is not None and not isinstance(metadata, dict):
            raise ValueError("metadata must be an object")
        artifact_id = str(uuid.uuid4())
        now = utc_now()
        def insert(db):
            db.execute("""
                INSERT INTO knowledge_artifacts
                (artifact_id, created_at, updated_at, artifact_type, title, content,
                 origin_brain, origin_version, sources_json, license_id, confidence,
                 status, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'proposed', ?)
            """, (artifact_id, now, now, artifact_type.strip(), title.strip(), content,
                  origin_brain.strip(), origin_version.strip(), json.dumps(sources, ensure_ascii=False),
                  license_id.strip(), float(confidence), json.dumps(metadata or {}, ensure_ascii=False)))
        if connection is not None:
            insert(connection)
            row = connection.execute(
                "SELECT * FROM knowledge_artifacts WHERE artifact_id = ?", (artifact_id,)
            ).fetchone()
            return self._decode(row)
        with closing(self._connect()) as db, db:
            insert(db)
        return self.get(artifact_id)

    def set_source_validator(self, validator) -> None:
        if validator is not None and not callable(validator):
            raise ValueError("source_validator_must_be_callable")
        self.source_validator = validator

    def transition(self, artifact_id: str, status: str, *, reviewer_id: str | None = None,
                   review_note: str | None = None,
                   license_decision: str | None = None) -> dict:
        """Advance an artifact only with an auditable human review at trust boundaries."""
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT * FROM knowledge_artifacts WHERE artifact_id = ?",
                             (artifact_id,)).fetchone()
            if row is None:
                raise KeyError(artifact_id)
            current = row["status"]
            if status not in self._transitions.get(current, set()):
                raise ValueError(f"Invalid knowledge transition: {current} -> {status}")

            requires_review = status in {"validated", "approved", "published"}
            if requires_review:
                if not isinstance(reviewer_id, str) or not reviewer_id.strip() or len(reviewer_id) > 120:
                    raise ValueError("human_reviewer_id_required")
                if not isinstance(review_note, str) or not review_note.strip() or len(review_note) > 2000:
                    raise ValueError("human_review_note_required")

            artifact = self._decode(row)
            metadata = artifact["metadata"]
            if status == "validated":
                if license_decision != "approved":
                    raise ValueError("explicit_license_approval_required")
                if artifact["license_id"] not in {"review_required", "approved"}:
                    raise ValueError("restricted_or_unknown_license_blocks_validation")
                if not artifact["sources"]:
                    raise ValueError("knowledge_artifact_requires_source_before_validation")
                if self.source_validator is None or not all(
                    self.source_validator(source_id) for source_id in artifact["sources"]
                ):
                    raise ValueError("knowledge_sources_must_exist_and_be_license_reviewed")
                artifact["license_id"] = "approved"
            elif status in {"approved", "published"} and artifact["license_id"] != "approved":
                raise ValueError("approved_license_required_before_approval_or_publication")

            if requires_review:
                reviews = metadata.setdefault("human_reviews", [])
                reviews.append({
                    "status": status,
                    "reviewer_id": reviewer_id.strip(),
                    "review_note": review_note.strip(),
                    "license_decision": license_decision if status == "validated" else None,
                    "reviewed_at": utc_now(),
                })
            db.execute(
                "UPDATE knowledge_artifacts SET status=?, license_id=?, metadata_json=?, updated_at=? "
                "WHERE artifact_id=?",
                (status, artifact["license_id"], json.dumps(metadata, ensure_ascii=False),
                 utc_now(), artifact_id),
            )
        return self.get(artifact_id)

    def get(self, artifact_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM knowledge_artifacts WHERE artifact_id = ?", (artifact_id,)).fetchone()
        return self._decode(row) if row else None

    def list(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        with closing(self._connect()) as db:
            if status:
                rows = db.execute("SELECT * FROM knowledge_artifacts WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                                   (status, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM knowledge_artifacts ORDER BY created_at DESC LIMIT ?",
                                   (limit,)).fetchall()
        return [self._decode(row) for row in rows]

    @staticmethod
    def _decode(row) -> dict:
        return {
            "artifact_id": row["artifact_id"], "created_at": row["created_at"],
            "updated_at": row["updated_at"], "artifact_type": row["artifact_type"],
            "title": row["title"], "content": row["content"],
            "origin_brain": row["origin_brain"], "origin_version": row["origin_version"],
            "sources": json.loads(row["sources_json"]), "license_id": row["license_id"],
            "confidence": row["confidence"], "status": row["status"],
            "metadata": json.loads(row["metadata_json"]),
        }
