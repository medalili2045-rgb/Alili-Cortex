"""AC Universal Library Foundry v1.

A fail-closed registry for third-party libraries. It records provenance and
artifact fingerprints; it never downloads, installs, imports, or executes code.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")
_ALLOWED_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "0BSD", "CC0-1.0", "Unlicense",
}
_BRAINS = {
    "reasoning", "code", "science", "research", "vision", "media",
    "language", "strategy", "memory", "execution", "learning_factory",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class LibraryFoundry:
    """Persistent library metadata registry with quarantine-first admission."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self):
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS ac_libraries (
                    library_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    version TEXT NOT NULL,
                    ecosystem TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    source_commit TEXT,
                    license_id TEXT,
                    license_status TEXT NOT NULL,
                    artifact_sha256 TEXT,
                    artifact_size INTEGER,
                    domains_json TEXT NOT NULL,
                    brains_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    review_notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_ac_libraries_status ON ac_libraries(status)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_ac_libraries_hash ON ac_libraries(artifact_sha256)")

    @staticmethod
    def fingerprint(data: bytes) -> dict:
        if not isinstance(data, bytes):
            raise TypeError("artifact_must_be_bytes")
        return {"sha256": hashlib.sha256(data).hexdigest(), "size_bytes": len(data)}

    def register(self, *, library_id: str, name: str, version: str,
                 ecosystem: str, source_url: str, license_id: str | None = None,
                 source_commit: str | None = None, artifact: bytes | None = None,
                 domains: list[str] | None = None, brains: list[str] | None = None,
                 license_approval: dict | None = None) -> dict:
        if not isinstance(library_id, str) or not _ID.fullmatch(library_id):
            raise ValueError("invalid_library_id")
        for key, value in (("name", name), ("version", version),
                           ("ecosystem", ecosystem), ("source_url", source_url)):
            if not isinstance(value, str) or not value.strip() or len(value) > 500:
                raise ValueError(f"invalid_{key}")
        if not source_url.startswith(("https://", "http://")):
            raise ValueError("source_url_must_be_http")
        domains = domains or []
        brains = brains or []
        if not all(isinstance(x, str) and x.strip() for x in domains):
            raise ValueError("invalid_domains")
        if not all(x in _BRAINS for x in brains):
            raise ValueError("unknown_brain_assignment")
        fp = self.fingerprint(artifact) if artifact is not None else {}
        approved = (
            license_id in _ALLOWED_LICENSES
            and isinstance(license_approval, dict)
            and license_approval.get("reviewed") is True
            and license_approval.get("artifact_scope") in {
                "source_code", "documentation", "dataset", "model_weights", "package"
            }
            and isinstance(license_approval.get("reviewer"), str)
            and bool(license_approval.get("reviewer").strip())
            and isinstance(license_approval.get("evidence_ref"), str)
            and license_approval.get("evidence_ref").startswith("https://")
        )
        license_status = "approved" if approved else "review_required"
        status = "approved" if approved else "quarantined"
        now = _utc_now()
        with self._connect() as db:
            if fp.get("sha256"):
                duplicate = db.execute(
                    "SELECT library_id FROM ac_libraries WHERE artifact_sha256=?",
                    (fp["sha256"],)
                ).fetchone()
                if duplicate:
                    raise ValueError("duplicate_artifact:" + duplicate["library_id"])
            db.execute("""
                INSERT INTO ac_libraries (
                    library_id,name,version,ecosystem,source_url,source_commit,
                    license_id,license_status,artifact_sha256,artifact_size,
                    domains_json,brains_json,status,review_notes,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (library_id, name.strip(), version.strip(), ecosystem.strip(),
                  source_url, source_commit, license_id, license_status,
                  fp.get("sha256"), fp.get("size_bytes"),
                  json.dumps(sorted(set(domains))), json.dumps(sorted(set(brains))),
                  status, None if approved else "explicit_license_review_required",
                  now, now))
        return self.get(library_id)

    def get(self, library_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM ac_libraries WHERE library_id=?",
                             (library_id,)).fetchone()
        return self._decode(row) if row else None

    def list(self, *, status: str | None = None, domain: str | None = None,
             brain: str | None = None, query: str | None = None,
             limit: int = 100) -> list[dict]:
        if not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("invalid_library_limit")
        if status and status not in {"quarantined", "approved", "rejected"}:
            raise ValueError("invalid_library_status")
        if brain and brain not in _BRAINS:
            raise ValueError("unknown_brain")
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM ac_libraries ORDER BY name COLLATE NOCASE LIMIT ?",
                (limit,)
            ).fetchall()
        items = [self._decode(row) for row in rows]
        q = query.casefold() if query else None
        return [item for item in items
                if (not status or item["status"] == status)
                and (not domain or domain in item["domains"])
                and (not brain or brain in item["brains"])
                and (not q or q in (item["name"] + " " + item["library_id"] + " " + item["ecosystem"]).casefold())]

    def review(self, library_id: str, *, decision: str, reviewer: str,
               evidence_ref: str, notes: str = "") -> dict:
        if decision not in {"approve", "reject"}:
            raise ValueError("invalid_review_decision")
        item = self.get(library_id)
        if item is None:
            raise KeyError("library_not_found")
        if not reviewer.strip() or not evidence_ref.startswith("https://"):
            raise ValueError("reviewer_and_https_evidence_required")
        if decision == "approve" and item["license_id"] not in _ALLOWED_LICENSES:
            raise ValueError("license_not_in_allowlist")
        status = "approved" if decision == "approve" else "rejected"
        license_status = "approved" if decision == "approve" else "rejected"
        with self._connect() as db:
            db.execute("""
                UPDATE ac_libraries SET status=?, license_status=?, review_notes=?,
                    updated_at=? WHERE library_id=?
            """, (status, license_status,
                  json.dumps({"reviewer": reviewer, "evidence_ref": evidence_ref,
                              "notes": notes}, ensure_ascii=False),
                  _utc_now(), library_id))
        return self.get(library_id)

    def summary(self) -> dict:
        with self._connect() as db:
            rows = db.execute("SELECT status, COUNT(*) AS n FROM ac_libraries GROUP BY status").fetchall()
        counts = {row["status"]: row["n"] for row in rows}
        return {
            "total": sum(counts.values()), "by_status": counts,
            "installations": 0, "code_execution": "disabled",
            "network_fetch": "disabled", "auto_approval": "disabled",
            "unknown_license": "quarantined",
        }

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["domains"] = json.loads(item.pop("domains_json"))
        item["brains"] = json.loads(item.pop("brains_json"))
        return item
