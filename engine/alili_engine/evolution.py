"""AC Evolution Engine: evidence-gated growth proposals for native knowledge and brains.

The engine proposes new libraries and specialist brains from identified knowledge
gaps. It never creates executable agents, installs packages, or self-approves changes.
"""
from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

_ID = re.compile(r"^[a-z][a-z0-9_-]{2,79}$")
_DOMAINS = {
    "software", "artificial_intelligence", "mathematics", "science", "engineering",
    "databases", "cloud", "security_defense", "research", "languages", "education",
    "robotics", "design", "biology", "medicine", "chemistry", "physics", "astronomy",
    "geography", "history", "economics", "law", "public_policy", "environment",
    "climate", "energy", "agriculture", "manufacturing", "electronics",
    "telecommunications", "transportation", "aerospace", "materials", "humanities",
    "ethics", "accessibility", "productivity", "business", "operations", "open_data",
    "standards",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ACEvolutionEngine:
    """Persistent proposal queue for controlled, knowledge-driven AC expansion."""

    VERSION = "1.0.0"
    MAX_TEXT = 4000

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.database_path, timeout=10) as db:
            db.execute("""CREATE TABLE IF NOT EXISTS ac_evolution_proposals (
                proposal_id TEXT PRIMARY KEY, proposal_type TEXT NOT NULL,
                item_id TEXT NOT NULL UNIQUE, name TEXT NOT NULL, domain TEXT NOT NULL,
                rationale TEXT NOT NULL, evidence_refs_json TEXT NOT NULL,
                status TEXT NOT NULL, review_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")

    @staticmethod
    def _text(value, field):
        if not isinstance(value, str) or not value.strip() or len(value) > ACEvolutionEngine.MAX_TEXT:
            raise ValueError("invalid_" + field)
        return value.strip()

    def propose(self, *, proposal_type: str, item_id: str, name: str,
                domain: str, rationale: str, evidence_refs: list[str]) -> dict:
        if proposal_type not in {"knowledge_library", "specialist_brain"}:
            raise ValueError("invalid_proposal_type")
        if not isinstance(item_id, str) or not _ID.fullmatch(item_id):
            raise ValueError("invalid_item_id")
        name = self._text(name, "name")
        rationale = self._text(rationale, "rationale")
        if domain not in _DOMAINS:
            raise ValueError("unknown_domain")
        if not isinstance(evidence_refs, list) or not evidence_refs or len(evidence_refs) > 20:
            raise ValueError("evidence_refs_required")
        refs = []
        for ref in evidence_refs:
            if not isinstance(ref, str) or not ref.startswith("https://") or len(ref) > 2048:
                raise ValueError("https_evidence_refs_required")
            refs.append(ref)
        now = _now()
        proposal_id = "ac-evo-" + uuid4().hex[:20]
        try:
            with sqlite3.connect(self.database_path, timeout=10) as db:
                db.execute("""INSERT INTO ac_evolution_proposals
                    (proposal_id, proposal_type, item_id, name, domain, rationale,
                     evidence_refs_json, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'pending_review', ?, ?)""",
                    (proposal_id, proposal_type, item_id, name, domain, rationale,
                     json.dumps(refs), now, now))
        except sqlite3.IntegrityError as exc:
            raise ValueError("duplicate_evolution_item") from exc
        return self.get(proposal_id)

    def get(self, proposal_id: str) -> dict | None:
        with sqlite3.connect(self.database_path, timeout=10) as db:
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM ac_evolution_proposals WHERE proposal_id=?",
                             (proposal_id,)).fetchone()
        return self._decode(row) if row else None

    @staticmethod
    def _decode(row) -> dict:
        item = dict(row)
        item["evidence_refs"] = json.loads(item.pop("evidence_refs_json"))
        return item

    def list(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        if status and status not in {"pending_review", "approved", "rejected"}:
            raise ValueError("invalid_evolution_status")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("invalid_evolution_limit")
        sql = "SELECT * FROM ac_evolution_proposals"
        params = ()
        if status:
            sql += " WHERE status=?"
            params = (status,)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params += (limit,)
        with sqlite3.connect(self.database_path, timeout=10) as db:
            db.row_factory = sqlite3.Row
            return [self._decode(row) for row in db.execute(sql, params).fetchall()]

    def review(self, proposal_id: str, *, decision: str, reviewer: str,
               notes: str = "") -> dict:
        if decision not in {"approve", "reject"}:
            raise ValueError("invalid_evolution_decision")
        reviewer = self._text(reviewer, "reviewer")
        notes = notes if isinstance(notes, str) and len(notes) <= self.MAX_TEXT else None
        if notes is None:
            raise ValueError("invalid_review_notes")
        with sqlite3.connect(self.database_path, timeout=10) as db:
            row = db.execute("SELECT status FROM ac_evolution_proposals WHERE proposal_id=?",
                             (proposal_id,)).fetchone()
            if row is None:
                raise KeyError("evolution_proposal_not_found")
            if row[0] != "pending_review":
                raise ValueError("evolution_proposal_already_reviewed")
            db.execute("""UPDATE ac_evolution_proposals SET status=?, review_notes=?, updated_at=?
                          WHERE proposal_id=?""",
                       ("approved" if decision == "approve" else "rejected",
                        f"reviewer={reviewer}; {notes}".strip(), _now(), proposal_id))
        return self.get(proposal_id)

    def status(self) -> dict:
        items = self.list(limit=200)
        counts = {key: sum(1 for item in items if item["status"] == key)
                  for key in ("pending_review", "approved", "rejected")}
        return {"available": True, "version": self.VERSION, "proposal_counts": counts,
                "automatic_creation": False, "automatic_brain_activation": False,
                "automatic_publication": False, "requires_human_review": True}
