"""Independent 24/7 scheduler and bounded autonomous study worker for AC.

The worker is a separate process. It never starts implicitly inside the HTTP API.
Fetched material is quarantined; resulting knowledge stays proposed for review.
"""
import argparse
import hashlib
import logging
from contextlib import closing
import json
import os
import sqlite3
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .api import build_service
from .study import MAX_EVIDENCE_CHARS

DEFAULT_INTERVAL_SECONDS = 24 * 60 * 60
DEFAULT_MAX_DOCUMENTS = 3
LOCK_LEASE_SECONDS = 15 * 60
LOGGER = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def _stamp(value=None):
    return (value or _now()).isoformat()


class AutonomousLearningWorker:
    """Runs bounded, resumable, provenance-preserving study cycles."""

    def __init__(self, service, database_path, *, interval_seconds=DEFAULT_INTERVAL_SECONDS,
                 max_documents=DEFAULT_MAX_DOCUMENTS):
        if isinstance(interval_seconds, bool) or not isinstance(interval_seconds, int) or interval_seconds < 3600:
            raise ValueError("interval_seconds_must_be_at_least_one_hour")
        if isinstance(max_documents, bool) or not isinstance(max_documents, int) or not 1 <= max_documents <= 20:
            raise ValueError("max_documents_must_be_1_to_20")
        self.service = service
        self.database_path = str(database_path)
        self.interval_seconds = interval_seconds
        self.max_documents = max_documents
        Path(self.database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self.worker_id = "acworker_" + uuid.uuid4().hex
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self):
        with closing(self._connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS ac_autonomous_state (
                    singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    paused INTEGER NOT NULL DEFAULT 0,
                    next_source_index INTEGER NOT NULL DEFAULT 0,
                    last_cycle_at TEXT,
                    last_cycle_status TEXT
                );
                INSERT OR IGNORE INTO ac_autonomous_state(singleton) VALUES(1);
                CREATE TABLE IF NOT EXISTS ac_autonomous_sources (
                    source_id TEXT PRIMARY KEY,
                    content_sha256 TEXT,
                    etag TEXT,
                    last_modified TEXT,
                    last_checked_at TEXT,
                    last_status TEXT
                );
                CREATE TABLE IF NOT EXISTS ac_autonomous_runs (
                    run_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    status TEXT NOT NULL,
                    scanned INTEGER NOT NULL DEFAULT 0,
                    fetched INTEGER NOT NULL DEFAULT 0,
                    studied INTEGER NOT NULL DEFAULT 0,
                    proposed INTEGER NOT NULL DEFAULT 0,
                    skipped INTEGER NOT NULL DEFAULT 0,
                    errors_json TEXT NOT NULL DEFAULT '[]'
                );
                CREATE TABLE IF NOT EXISTS ac_autonomous_lock (
                    lock_name TEXT PRIMARY KEY,
                    owner_id TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                );
            """)

    def set_paused(self, paused):
        with closing(self._connect()) as db, db:
            db.execute("UPDATE ac_autonomous_state SET paused=? WHERE singleton=1",
                       (1 if paused else 0,))
        return self.status()

    def status(self):
        with closing(self._connect()) as db, db:
            state = dict(db.execute("SELECT * FROM ac_autonomous_state WHERE singleton=1").fetchone())
            latest = db.execute(
                "SELECT * FROM ac_autonomous_runs ORDER BY started_at DESC LIMIT 1").fetchone()
        return {
            "worker": "AC Autonomous Learning Worker",
            "mode": "independent_process",
            "interval_seconds": self.interval_seconds,
            "interval_hours": self.interval_seconds / 3600,
            "max_documents_per_cycle": self.max_documents,
            "paused": bool(state["paused"]),
            "next_source_index": state["next_source_index"],
            "last_cycle_at": state["last_cycle_at"],
            "last_cycle_status": state["last_cycle_status"],
            "latest_run": dict(latest) if latest else None,
            "publication": "human_approval_required",
            "weights_training": "not_performed",
        }

    def _acquire_lock(self):
        now = _now()
        expires = now + timedelta(seconds=LOCK_LEASE_SECONDS)
        with closing(self._connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT owner_id, expires_at FROM ac_autonomous_lock WHERE lock_name='cycle'").fetchone()
            if row and row["expires_at"] > _stamp(now):
                db.rollback()
                return False
            db.execute("""
                INSERT INTO ac_autonomous_lock(lock_name, owner_id, expires_at)
                VALUES('cycle', ?, ?)
                ON CONFLICT(lock_name) DO UPDATE SET owner_id=excluded.owner_id,
                    expires_at=excluded.expires_at
            """, (self.worker_id, _stamp(expires)))
        return True

    def _refresh_lock(self):
        """Extend this worker's lease; return False if another worker owns the cycle."""
        expires = _stamp(_now() + timedelta(seconds=LOCK_LEASE_SECONDS))
        with closing(self._connect()) as db, db:
            cursor = db.execute(
                "UPDATE ac_autonomous_lock SET expires_at=? "
                "WHERE lock_name='cycle' AND owner_id=?",
                (expires, self.worker_id))
            return cursor.rowcount == 1

    def _release_lock(self):
        with closing(self._connect()) as db, db:
            db.execute("DELETE FROM ac_autonomous_lock WHERE lock_name='cycle' AND owner_id=?",
                       (self.worker_id,))

    def _source_checkpoint(self, source_id):
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT * FROM ac_autonomous_sources WHERE source_id=?",
                             (source_id,)).fetchone()
        return dict(row) if row else {}

    def _save_source_checkpoint(self, source_id, *, digest=None, etag=None,
                                last_modified=None, status):
        with closing(self._connect()) as db, db:
            db.execute("""
                INSERT INTO ac_autonomous_sources
                (source_id, content_sha256, etag, last_modified, last_checked_at, last_status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    content_sha256=COALESCE(excluded.content_sha256, ac_autonomous_sources.content_sha256),
                    etag=COALESCE(excluded.etag, ac_autonomous_sources.etag),
                    last_modified=COALESCE(excluded.last_modified, ac_autonomous_sources.last_modified),
                    last_checked_at=excluded.last_checked_at, last_status=excluded.last_status
            """, (source_id, digest, etag, last_modified, _stamp(), status))

    def _study_source(self, source):
        source_id = source["source_id"]
        checkpoint = self._source_checkpoint(source_id)
        fetched = self.service.connectors.fetch(
            source_id, if_none_match=checkpoint.get("etag"),
            if_modified_since=checkpoint.get("last_modified"))
        if fetched.get("not_modified"):
            self._save_source_checkpoint(source_id, etag=fetched.get("etag"),
                                         last_modified=fetched.get("last_modified"),
                                         status="not_modified")
            return "skipped"
        full_digest = fetched.get("sha256")
        if not isinstance(full_digest, str) or len(full_digest) != 64:
            full_digest = hashlib.sha256(fetched["content"].encode("utf-8")).hexdigest()
        if full_digest == checkpoint.get("content_sha256"):
            self._save_source_checkpoint(source_id, digest=full_digest, etag=fetched.get("etag"),
                                         last_modified=fetched.get("last_modified"),
                                         status="unchanged")
            return "skipped"

        content = fetched["content"][:MAX_EVIDENCE_CHARS]
        stored_digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        # Reuse a prior snapshot when a cycle failed after evidence intake.
        existing = next((item for item in self.service.list_study_evidence(
            source_id=source_id, limit=100
        ) if item["sha256"] == stored_digest), None)
        evidence = (self.service.get_study_evidence(existing["evidence_id"])
                    if existing else None)
        if evidence is None:
            evidence = self.service.add_study_evidence(
                source_id=source_id, title=(fetched["title"] or source["name"])[:300],
                content=content, artifact_url=fetched["artifact_url"],
                version=fetched["version"][:200], license_status="review_required")
        focus = source.get("study_focus") or source.get("domains") or ["general concepts"]
        focus_text = ", ".join(str(item) for item in focus[:8])
        question = (
            f"Study the public official material for {source['name']}. "
            f"Focus: {focus_text}. Identify concepts, interfaces, constraints, "
            "security considerations and unanswered questions. This is evidence triage, "
            "not semantic verification."
        )
        session = self.service.create_study_session(
            question=question[:2000], evidence_ids=[evidence["evidence_id"]],
            domain=(source.get("domains") or ["general"])[0][:100])
        evaluated = self.service.evaluate_study_session(session["session_id"])
        proposed = False
        if evaluated["evaluation"].get("status") == "structural_checks_passed_human_review_required":
            self.service.propose_study_knowledge(
                session["session_id"], origin_brain="ac_research")
            proposed = True
        self._save_source_checkpoint(source_id, digest=full_digest, etag=fetched.get("etag"),
                                     last_modified=fetched.get("last_modified"),
                                     status="proposed_for_review" if proposed else "studied_quarantined")
        return "proposed" if proposed else "studied"

    def run_cycle(self):
        if not self._acquire_lock():
            return {"status": "skipped_lock_held", "worker_id": self.worker_id}
        run_id = "acrun_" + uuid.uuid4().hex
        started = _stamp()
        counts = {"scanned": 0, "fetched": 0, "studied": 0, "proposed": 0, "skipped": 0}
        errors = []
        status = "running"
        LOGGER.info("AC learning cycle started: run_id=%s worker_id=%s", run_id, self.worker_id)
        try:
            with closing(self._connect()) as db, db:
                db.execute("INSERT INTO ac_autonomous_runs(run_id, started_at, status) VALUES(?, ?, 'running')",
                           (run_id, started))
                state = db.execute("SELECT paused, next_source_index FROM ac_autonomous_state WHERE singleton=1").fetchone()
            if state["paused"]:
                status = "paused"
                return {"run_id": run_id, "status": status, **counts}
            sources = self.service.ecosystem_catalog(limit=200)
            if not sources:
                status = "no_catalog_sources"
                return {"run_id": run_id, "status": status, **counts}
            start = state["next_source_index"] % len(sources)
            indexes = [(start + offset) % len(sources) for offset in range(len(sources))]
            for index in indexes:
                if counts["fetched"] >= self.max_documents or counts["scanned"] >= self.max_documents * 3:
                    break
                if not self._refresh_lock():
                    status = "lock_lost"
                    errors.append({"error": "cycle_lock_lease_lost"})
                    break
                source = sources[index]
                counts["scanned"] += 1
                try:
                    outcome = self._study_source(source)
                    if outcome == "skipped":
                        counts["skipped"] += 1
                    else:
                        counts["fetched"] += 1
                        counts["studied"] += 1
                        if outcome == "proposed":
                            counts["proposed"] += 1
                    with closing(self._connect()) as db, db:
                        db.execute("UPDATE ac_autonomous_state SET next_source_index=? WHERE singleton=1",
                                   ((index + 1) % len(sources),))
                except Exception as exc:
                    errors.append({"source_id": source.get("source_id"), "error": str(exc)[:300]})
                    self._save_source_checkpoint(source["source_id"], status="error")
                    with closing(self._connect()) as db, db:
                        db.execute("UPDATE ac_autonomous_state SET next_source_index=? WHERE singleton=1",
                                   ((index + 1) % len(sources),))
            if errors and status != "lock_lost":
                status = "completed_with_errors"
            elif status == "running":
                status = "completed"
            return {"run_id": run_id, "status": status, **counts, "errors": errors}
        except Exception:
            status = "failed"
            LOGGER.exception("AC learning cycle failed: run_id=%s", run_id)
            raise
        finally:
            finished = _stamp()
            with closing(self._connect()) as db, db:
                row = db.execute("SELECT run_id FROM ac_autonomous_runs WHERE run_id=?", (run_id,)).fetchone()
                if row:
                    db.execute("""
                        UPDATE ac_autonomous_runs SET finished_at=?, status=?,
                            scanned=?, fetched=?, studied=?, proposed=?, skipped=?, errors_json=?
                        WHERE run_id=?
                    """, (finished, status, counts["scanned"], counts["fetched"],
                          counts["studied"], counts["proposed"], counts["skipped"],
                          json.dumps(errors, ensure_ascii=False), run_id))
                    db.execute("UPDATE ac_autonomous_state SET last_cycle_at=?, last_cycle_status=? WHERE singleton=1",
                               (finished, status))
            self._release_lock()
            LOGGER.info("AC learning cycle finished: run_id=%s status=%s counts=%s",
                        run_id, status, counts)

    def run_forever(self, *, run_immediately=True):
        if run_immediately:
            self.run_cycle()
        while True:
            remaining = self.interval_seconds
            while remaining > 0:
                time.sleep(min(60, remaining))
                remaining -= min(60, remaining)
            self.run_cycle()


def main(argv=None):
    parser = argparse.ArgumentParser(description="AC independent autonomous learning worker")
    parser.add_argument("--db-path", default=os.environ.get("ALILI_ENGINE_DB_PATH", "./data/jobs.sqlite3"))
    parser.add_argument("--interval-hours", type=int, default=24)
    parser.add_argument("--max-documents", type=int, default=3)
    parser.add_argument("--once", action="store_true", help="run one study cycle and exit")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--pause", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    # The service and scheduler must share the exact same SQLite database.
    os.environ["ALILI_ENGINE_DB_PATH"] = args.db_path
    service = build_service()
    worker = AutonomousLearningWorker(
        service, args.db_path, interval_seconds=args.interval_hours * 3600,
        max_documents=args.max_documents)
    if args.pause:
        print(json.dumps(worker.set_paused(True), ensure_ascii=False))
        return 0
    if args.resume:
        print(json.dumps(worker.set_paused(False), ensure_ascii=False))
        return 0
    if args.status:
        print(json.dumps(worker.status(), ensure_ascii=False))
        return 0
    if args.once:
        print(json.dumps(worker.run_cycle(), ensure_ascii=False))
        return 0
    worker.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
