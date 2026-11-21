"""AC Knowledge Scout v1: safe, provenance-first knowledge discovery queue.

This core manages approved public-source registrations, resumable discovery jobs,
and quarantined knowledge proposals. It deliberately performs no network fetch,
scraping, model inference, package installation, or automatic publication.
"""
from __future__ import annotations

import hashlib
import ipaddress
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

_SOURCE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{1,79}$")
_BRAINS = {
    "reasoning", "code", "science", "research", "vision", "media",
    "language", "strategy", "memory", "execution", "learning_factory",
}
_DOMAINS = {
    "software", "artificial_intelligence", "mathematics", "science",
    "engineering", "databases", "cloud", "security_defense", "research",
    "languages", "education", "robotics", "design", "biology", "medicine",
    "chemistry", "physics", "astronomy", "geography", "history", "economics",
    "law", "public_policy", "environment", "climate", "energy", "agriculture",
    "manufacturing", "electronics", "telecommunications", "transportation",
    "aerospace", "materials", "humanities", "ethics", "accessibility",
    "productivity", "business", "operations", "open_data", "standards",
}
_MAX_NOTE_CHARS = 12_000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_public_https_url(url: str) -> str:
    """Validate URL syntax and reject local/private destinations.

    Actual network fetching must additionally pin and validate resolved IPs on
    every redirect; this function alone is not an SSRF-proof fetcher.
    """
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError("invalid_source_url")
    try:
        parsed = urlsplit(url.strip())
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid_source_url") from exc
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or parsed.fragment or port not in (None, 443)):
        raise ValueError("public_https_url_required")
    host = host.rstrip(".").lower()
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        raise ValueError("private_destination_forbidden")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)(?:\.(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?))*", host):
            raise ValueError("invalid_source_host")
    else:
        if not address.is_global:
            raise ValueError("private_destination_forbidden")
    return parsed.geturl()


class KnowledgeScout:
    """SQLite-backed source registry, resumable queue and quarantine inbox."""

    def __init__(self, database_path: str | Path):
        self.database_path = str(database_path)
        self._initialize()

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _initialize(self):
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS ac_scout_sources (
                source_id TEXT PRIMARY KEY, name TEXT NOT NULL, base_url TEXT NOT NULL,
                source_type TEXT NOT NULL, domains_json TEXT NOT NULL,
                brains_json TEXT NOT NULL, terms_reviewed INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL)""")
            db.execute("""CREATE TABLE IF NOT EXISTS ac_scout_jobs (
                job_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, query TEXT NOT NULL,
                status TEXT NOT NULL, checkpoint_json TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES ac_scout_sources(source_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS ac_scout_proposals (
                proposal_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, title TEXT NOT NULL,
                note TEXT NOT NULL, content_sha256 TEXT NOT NULL UNIQUE,
                provenance_json TEXT NOT NULL, domain TEXT NOT NULL, brain_id TEXT NOT NULL,
                status TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(source_id) REFERENCES ac_scout_sources(source_id))""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_ac_scout_jobs_status ON ac_scout_jobs(status)")
            db.execute("CREATE INDEX IF NOT EXISTS idx_ac_scout_proposals_status ON ac_scout_proposals(status)")

    def register_source(self, *, source_id: str, name: str, base_url: str,
                        source_type: str, domains: list[str], brains: list[str],
                        terms_reviewed: bool = False) -> dict:
        if not isinstance(source_id, str) or not _SOURCE_ID.fullmatch(source_id):
            raise ValueError("invalid_source_id")
        if not isinstance(name, str) or not name.strip() or len(name) > 200:
            raise ValueError("invalid_source_name")
        safe_url = validate_public_https_url(base_url)
        if source_type not in {"official_docs", "open_access_research", "public_repository",
                               "educational_resource", "public_dataset", "standards_body",
                               "government_open_data", "academic_repository",
                               "open_courseware", "security_advisory", "open_source_project"}:
            raise ValueError("unsupported_source_type")
        if not isinstance(domains, list) or not domains or not set(domains) <= _DOMAINS:
            raise ValueError("invalid_source_domains")
        if not isinstance(brains, list) or not set(brains) <= _BRAINS:
            raise ValueError("invalid_brain_assignment")
        if not isinstance(terms_reviewed, bool):
            raise ValueError("invalid_terms_reviewed")
        now = _now()
        with self._connect() as db:
            db.execute("""INSERT INTO ac_scout_sources
                (source_id,name,base_url,source_type,domains_json,brains_json,
                 terms_reviewed,enabled,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (source_id, name.strip(), safe_url, source_type,
                 json.dumps(sorted(set(domains))), json.dumps(sorted(set(brains))),
                 int(terms_reviewed), 0, now, now))
        return self.get_source(source_id)

    def get_source(self, source_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM ac_scout_sources WHERE source_id=?", (source_id,)).fetchone()
        return self._decode_source(row) if row else None

    def list_sources(self, *, enabled: bool | None = None, limit: int = 100) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("invalid_scout_limit")
        with self._connect() as db:
            rows = db.execute("SELECT * FROM ac_scout_sources ORDER BY name LIMIT ?", (limit,)).fetchall()
        items = [self._decode_source(row) for row in rows]
        return [item for item in items if enabled is None or item["enabled"] is enabled]

    def set_source_enabled(self, source_id: str, enabled: bool, *, terms_evidence_url: str | None = None) -> dict:
        if not isinstance(enabled, bool):
            raise ValueError("invalid_enabled_flag")
        source = self.get_source(source_id)
        if source is None:
            raise KeyError("scout_source_not_found")
        if enabled:
            if not source["terms_reviewed"]:
                raise ValueError("source_terms_review_required")
            if not terms_evidence_url:
                raise ValueError("terms_evidence_required")
            validate_public_https_url(terms_evidence_url)
        with self._connect() as db:
            db.execute("UPDATE ac_scout_sources SET enabled=?, updated_at=? WHERE source_id=?",
                       (int(enabled), _now(), source_id))
        return self.get_source(source_id)

    def enqueue(self, *, source_id: str, query: str) -> dict:
        source = self.get_source(source_id)
        if source is None:
            raise KeyError("scout_source_not_found")
        if not source["enabled"]:
            raise ValueError("scout_source_not_enabled")
        if not isinstance(query, str) or not query.strip() or len(query) > 500:
            raise ValueError("invalid_scout_query")
        job_id = "scout-" + hashlib.sha256(
            (source_id + "\0" + query.strip() + "\0" + _now()).encode()
        ).hexdigest()[:24]
        now = _now()
        with self._connect() as db:
            db.execute("""INSERT INTO ac_scout_jobs
                (job_id,source_id,query,status,checkpoint_json,attempts,created_at,updated_at)
                VALUES (?,?,?,'queued','{}',0,?,?)""",
                (job_id, source_id, query.strip(), now, now))
        return self.get_job(job_id)

    def get_job(self, job_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM ac_scout_jobs WHERE job_id=?", (job_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["checkpoint"] = json.loads(item.pop("checkpoint_json"))
        return item

    def list_jobs(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("invalid_scout_limit")
        if status and status not in {"queued", "running", "paused", "completed", "failed"}:
            raise ValueError("invalid_scout_job_status")
        with self._connect() as db:
            rows = db.execute("SELECT job_id FROM ac_scout_jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        items = [self.get_job(row["job_id"]) for row in rows]
        return [item for item in items if item and (not status or item["status"] == status)]

    def checkpoint_job(self, job_id: str, *, checkpoint: dict, status: str = "paused") -> dict:
        if status not in {"queued", "running", "paused", "completed", "failed"}:
            raise ValueError("invalid_scout_job_status")
        if not isinstance(checkpoint, dict) or len(json.dumps(checkpoint)) > 8000:
            raise ValueError("invalid_scout_checkpoint")
        with self._connect() as db:
            row = db.execute("SELECT attempts FROM ac_scout_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None:
                raise KeyError("scout_job_not_found")
            db.execute("""UPDATE ac_scout_jobs SET status=?,checkpoint_json=?,
                attempts=attempts+1,updated_at=? WHERE job_id=?""",
                (status, json.dumps(checkpoint, ensure_ascii=False), _now(), job_id))
        return self.get_job(job_id)

    def propose(self, *, source_id: str, title: str, note: str, domain: str,
                brain_id: str, source_url: str, retrieved_at: str | None = None,
                license_evidence_url: str | None = None) -> dict:
        source = self.get_source(source_id)
        if source is None:
            raise KeyError("scout_source_not_found")
        safe_url = validate_public_https_url(source_url)
        if not safe_url.startswith(source["base_url"].rstrip("/") + "/") and safe_url != source["base_url"]:
            raise ValueError("proposal_url_outside_registered_source")
        if not isinstance(title, str) or not title.strip() or len(title) > 300:
            raise ValueError("invalid_proposal_title")
        if not isinstance(note, str) or not note.strip() or len(note) > _MAX_NOTE_CHARS:
            raise ValueError("invalid_proposal_note")
        if domain not in source["domains"] or domain not in _DOMAINS:
            raise ValueError("proposal_domain_not_allowed")
        if brain_id not in source["brains"] or brain_id not in _BRAINS:
            raise ValueError("proposal_brain_not_allowed")
        if license_evidence_url:
            validate_public_https_url(license_evidence_url)
        normalized = note.strip()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        proposal_id = "proposal-" + digest[:24]
        provenance = {"source_id": source_id, "source_url": safe_url,
                      "retrieved_at": retrieved_at or _now(),
                      "license_evidence_url": license_evidence_url,
                      "content_sha256": digest, "content_kind": "short_note_or_summary"}
        try:
            with self._connect() as db:
                db.execute("""INSERT INTO ac_scout_proposals
                    (proposal_id,source_id,title,note,content_sha256,provenance_json,
                     domain,brain_id,status,created_at)
                    VALUES (?,?,?,?,?,?,?,?, 'quarantined',?)""",
                    (proposal_id, source_id, title.strip(), normalized, digest,
                     json.dumps(provenance, ensure_ascii=False), domain, brain_id, _now()))
        except sqlite3.IntegrityError as exc:
            raise ValueError("duplicate_knowledge_note") from exc
        return self.get_proposal(proposal_id)

    def get_proposal(self, proposal_id: str) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM ac_scout_proposals WHERE proposal_id=?", (proposal_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["provenance"] = json.loads(item.pop("provenance_json"))
        item["install_enabled"] = False
        return item

    def list_proposals(self, *, status: str | None = None, limit: int = 50) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("invalid_scout_limit")
        if status and status not in {"quarantined", "approved", "rejected"}:
            raise ValueError("invalid_scout_proposal_status")
        with self._connect() as db:
            rows = db.execute("SELECT proposal_id FROM ac_scout_proposals ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        items = [self.get_proposal(row["proposal_id"]) for row in rows]
        return [item for item in items if item and (not status or item["status"] == status)]

    def summary(self) -> dict:
        return {
            "module": "AC Knowledge Scout", "version": "1.1.0",
            "source_registry": "available", "network_fetch": "catalog_bound_dns_pinned_connector",
            "discovery_execution": "on_demand", "scheduler": "queue_and_checkpoint_only",
            "continuous_uptime_guaranteed": False, "automatic_publication": False,
            "automatic_installation": False, "paid_services": "prohibited",
            "bank_card_required_services": "prohibited",
            "sources": len(self.list_sources()),
            "queued_jobs": len(self.list_jobs(status="queued")),
            "quarantined_proposals": len(self.list_proposals(status="quarantined")),
        }

    @staticmethod
    def _decode_source(row: sqlite3.Row) -> dict:
        item = dict(row)
        item["domains"] = json.loads(item.pop("domains_json"))
        item["brains"] = json.loads(item.pop("brains_json"))
        item["terms_reviewed"] = bool(item["terms_reviewed"])
        item["enabled"] = bool(item["enabled"])
        return item
