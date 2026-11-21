"""Local-first, provenance-aware study intake and evidence review.

This v1 studies caller-supplied text only. It does not crawl the network, execute
retrieved code, infer license permission, or automatically publish knowledge.
"""
import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from .store import utc_now


MAX_EVIDENCE_CHARS = 64_000
MAX_EVIDENCE_ITEMS = 12
MAX_QUESTION_CHARS = 2_000
_STOP_WORDS = {
    # English
    "about", "after", "also", "and", "are", "for", "from", "into", "its",
    "that", "the", "their", "then", "this", "with", "what", "when", "where",
    "which", "will", "would", "your", "have", "has", "can", "not", "use",
    # French
    "avec", "dans", "des", "est", "les", "mais", "nous", "pour", "que",
    "qui", "sur", "une", "vous", "aux", "ces", "comme", "plus",
    # Arabic
    "هذا", "هذه", "ذلك", "تلك", "على", "الى", "إلى", "من", "عن", "في",
    "هو", "هي", "هم", "كما", "كان", "كانت", "مع", "ما", "ماذا", "كيف",
}


def _tokens(value: str) -> set[str]:
    """Return Unicode-aware tokens for Arabic, French, English and other scripts."""
    words = re.findall(r"[^\W_][\w+-]{1,}", value, flags=re.UNICODE)
    return {word.casefold() for word in words
            if word.casefold() not in _STOP_WORDS}


class UniversalStudyEngine:
    """Stores immutable evidence snapshots and creates auditable study reports."""

    def __init__(self, database_path: str, ecosystem_registry, knowledge_store):
        self._uri = database_path == ":memory:"
        self.database_path = (f"file:ac_study_{uuid.uuid4().hex}?mode=memory&cache=shared"
                              if self._uri else str(Path(database_path).expanduser()))
        if not self._uri:
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._keeper = self._connect() if self._uri else None
        self.ecosystem = ecosystem_registry
        self.knowledge = knowledge_store
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10, uri=self._uri)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self):
        with closing(self._connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS study_evidence (
                    evidence_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    source_id TEXT NOT NULL, title TEXT NOT NULL, artifact_url TEXT NOT NULL,
                    version TEXT NOT NULL, license_status TEXT NOT NULL,
                    content TEXT NOT NULL, sha256 TEXT NOT NULL, status TEXT NOT NULL
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_study_evidence_source ON study_evidence(source_id)")
            db.execute("""
                CREATE TABLE IF NOT EXISTS study_sessions (
                    session_id TEXT PRIMARY KEY, created_at TEXT NOT NULL,
                    question TEXT NOT NULL, domain TEXT NOT NULL,
                    evidence_ids_json TEXT NOT NULL, report_json TEXT NOT NULL,
                    evaluation_json TEXT NOT NULL
                )
            """)

    def add_evidence(self, *, source_id: str, title: str, content: str,
                     artifact_url: str = "", version: str = "unspecified",
                     license_status: str = "unknown", connection=None) -> dict:
        source = self.ecosystem.get(source_id)
        if source is None:
            raise ValueError("unknown_ecosystem_source")
        if not isinstance(title, str) or not title.strip() or len(title) > 300:
            raise ValueError("title_must_be_1_to_300_characters")
        if not isinstance(content, str) or not content.strip() or len(content) > MAX_EVIDENCE_CHARS:
            raise ValueError("content_must_be_1_to_64000_characters")
        if not isinstance(artifact_url, str) or len(artifact_url) > 2048:
            raise ValueError("invalid_artifact_url")
        if artifact_url and not artifact_url.startswith("https://"):
            raise ValueError("artifact_url_must_use_https")
        if not isinstance(version, str) or not version.strip() or len(version) > 200:
            raise ValueError("invalid_artifact_version")
        if not isinstance(license_status, str) or license_status not in {"unknown", "review_required", "approved", "restricted"}:
            raise ValueError("invalid_license_status")
        evidence_id = str(uuid.uuid4())
        created_at = utc_now()
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        # All new evidence starts quarantined, including items whose license is reported approved.
        def insert(db):
            db.execute("""
                INSERT INTO study_evidence
                (evidence_id, created_at, source_id, title, artifact_url, version,
                 license_status, content, sha256, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'quarantined')
            """, (evidence_id, created_at, source_id, title.strip(), artifact_url,
                  version.strip(), license_status, content, digest))
            row = db.execute("SELECT * FROM study_evidence WHERE evidence_id = ?",
                             (evidence_id,)).fetchone()
            return self._decode_evidence(row)
        if connection is not None:
            return insert(connection)
        with closing(self._connect()) as db, db:
            return insert(db)

    def get_evidence(self, evidence_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM study_evidence WHERE evidence_id = ?", (evidence_id,)).fetchone()
        return self._decode_evidence(row) if row else None

    def list_evidence(self, *, source_id: str | None = None, limit: int = 50) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit_must_be_between_1_and_100")
        with closing(self._connect()) as db:
            if source_id:
                rows = db.execute("SELECT * FROM study_evidence WHERE source_id = ? ORDER BY created_at DESC LIMIT ?",
                                   (source_id, limit)).fetchall()
            else:
                rows = db.execute("SELECT * FROM study_evidence ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decode_evidence(row, include_content=False) for row in rows]

    @staticmethod
    def _decode_evidence(row, include_content=True) -> dict:
        item = {
            "evidence_id": row["evidence_id"], "created_at": row["created_at"],
            "source_id": row["source_id"], "title": row["title"],
            "artifact_url": row["artifact_url"], "version": row["version"],
            "license_status": row["license_status"], "sha256": row["sha256"],
            "status": row["status"],
        }
        if include_content:
            item["content"] = row["content"]
        return item

    def create_session(self, *, question: str, evidence_ids: list[str], domain: str = "general", connection=None) -> dict:
        if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION_CHARS:
            raise ValueError("question_must_be_1_to_2000_characters")
        if not isinstance(evidence_ids, list) or not 1 <= len(evidence_ids) <= MAX_EVIDENCE_ITEMS:
            raise ValueError("evidence_ids_must_contain_1_to_12_items")
        if any(not isinstance(x, str) or not x for x in evidence_ids) or len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("evidence_ids_must_be_unique_strings")
        if not isinstance(domain, str) or not domain.strip() or len(domain) > 100:
            raise ValueError("invalid_study_domain")
        evidence = [self.get_evidence(item) for item in evidence_ids]
        if any(item is None for item in evidence):
            raise ValueError("study_evidence_not_found")
        terms = _tokens(question)
        findings = []
        for item in evidence:
            lines = [line.strip() for line in item["content"].splitlines() if line.strip()]
            ranked = sorted(
                enumerate(lines),
                key=lambda pair: (-len(terms.intersection(_tokens(pair[1]))), pair[0])
            )
            selected = [line for _, line in ranked[:5] if terms.intersection(_tokens(line))]
            findings.append({
                "evidence_id": item["evidence_id"], "source_id": item["source_id"],
                "title": item["title"], "sha256": item["sha256"],
                "license_status": item["license_status"],
                "candidate_passages": selected,
                "passage_selection": "deterministic_keyword_overlap_not_semantic_verification",
            })
        report = {
            "method": "local_deterministic_evidence_triage_v1",
            "question": question.strip(), "domain": domain.strip(),
            "evidence_count": len(evidence), "findings": findings,
            "cross_source_comparison": self._compare(findings),
            "limitations": [
                "This is evidence triage, not an AI-generated scientific conclusion.",
                "Candidate passages require human reading and source-context verification.",
                "No source content or code was fetched or executed by this engine.",
                "License metadata is recorded but permission is not granted by this record.",
            ],
            "status": "draft_requires_human_review",
        }
        session_id = str(uuid.uuid4())
        created_at = utc_now()
        def insert(db):
            db.execute("""
                INSERT INTO study_sessions
                (session_id, created_at, question, domain, evidence_ids_json, report_json, evaluation_json)
                VALUES (?, ?, ?, ?, ?, ?, '{}')
            """, (session_id, created_at, question.strip(), domain.strip(),
                  json.dumps(evidence_ids), json.dumps(report, ensure_ascii=False)))
        if connection is not None:
            insert(connection)
            return {
                "session_id": session_id, "created_at": created_at,
                "question": question.strip(), "domain": domain.strip(),
                "evidence_ids": evidence_ids, "report": report, "evaluation": {},
            }
        with closing(self._connect()) as db, db:
            insert(db)
        return self.get_session(session_id)

    @staticmethod
    def _compare(findings: list[dict]) -> dict:
        term_sets = []
        for finding in findings:
            term_sets.append(set().union(*(_tokens(text) for text in finding["candidate_passages"])))
        common = sorted(set.intersection(*term_sets)) if term_sets and all(term_sets) else []
        all_terms = set.union(*term_sets) if term_sets else set()
        return {
            "shared_terms": common[:30],
            "distinctive_terms": sorted(all_terms.difference(common))[:60],
            "interpretation": "lexical_overlap_only_not_claim_agreement",
        }

    def evaluate_session(self, session_id: str) -> dict:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        evidence = [self.get_evidence(item) for item in session["evidence_ids"]]
        checks = {
            "all_evidence_exists": all(item is not None for item in evidence),
            "evidence_hashes_match": all(bool(item and hashlib.sha256(item["content"].encode("utf-8")).hexdigest() == item["sha256"]) for item in evidence),
            "all_sources_in_catalog": all(bool(item and self.ecosystem.get(item["source_id"])) for item in evidence),
            "all_licenses_approved": all(bool(item and item["license_status"] == "approved") for item in evidence),
            "all_evidence_still_quarantined": all(bool(item and item["status"] == "quarantined") for item in evidence),
            "question_has_searchable_terms": bool(_tokens(session["question"])),
            "has_relevant_passages": any(
                bool(finding.get("candidate_passages"))
                for finding in session["report"].get("findings", [])
            ),
        }
        evaluation = {
            "checks": checks, "checks_passed": sum(checks.values()),
            "checks_total": len(checks),
            "status": "structural_checks_passed_human_review_required" if all(checks.values())
                      else "blocked_pending_license_provenance_or_relevance",
            "semantic_accuracy": "not_evaluated",
            "license_clearance": "not_granted",
            "production_approval": False,
        }
        with closing(self._connect()) as db, db:
            db.execute("UPDATE study_sessions SET evaluation_json = ? WHERE session_id = ?",
                       (json.dumps(evaluation, ensure_ascii=False), session_id))
        return self.get_session(session_id)

    def propose_knowledge(self, session_id: str, *, origin_brain: str = "ac_research", connection=None) -> dict:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        evaluation = session["evaluation"]
        if evaluation.get("status") != "structural_checks_passed_human_review_required":
            raise ValueError("study_session_must_pass_structural_checks_first")
        report = session["report"]
        return self.knowledge.propose(
            artifact_type="study_report", title=report["question"],
            content=json.dumps(report, ensure_ascii=False),
            origin_brain=origin_brain, origin_version="ac-universal-study-v1",
            sources=session["evidence_ids"], license_id="review_required",
            confidence=0.0, metadata={
                "study_session_id": session_id,
                "evaluation": evaluation,
                "publication_requires_human_approval": True,
            }, connection=connection)

    def get_session(self, session_id: str) -> dict | None:
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM study_sessions WHERE session_id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        return {
            "session_id": row["session_id"], "created_at": row["created_at"],
            "question": row["question"], "domain": row["domain"],
            "evidence_ids": json.loads(row["evidence_ids_json"]),
            "report": json.loads(row["report_json"]),
            "evaluation": json.loads(row["evaluation_json"]),
        }

    def list_sessions(self, limit: int = 50) -> list[dict]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit_must_be_between_1_and_100")
        with closing(self._connect()) as db:
            rows = db.execute("SELECT session_id FROM study_sessions ORDER BY created_at DESC LIMIT ?",
                              (limit,)).fetchall()
        return [self.get_session(row["session_id"]) for row in rows]
