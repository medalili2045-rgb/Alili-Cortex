"""Free-first hybrid training orchestration; no model weights or code are executed here."""
import json
import sqlite3
import uuid
from contextlib import closing
from pathlib import Path

from .store import utc_now

TRAINING_POLICY = {
    "learning_mode": "hybrid",
    "autonomy": "sandbox",
    "scope": "all",
    "paid_services": "forbidden",
    "hosted_fallback": "disabled",
    "weight_updates": "not_performed",
    "sandbox_execution": "not_implemented",
}

CURRICULA = (
    {"curriculum_id": "reasoning", "brain_id": "ac_reasoning", "domain": "logic and reasoning",
     "objectives": ["argument analysis", "multi-step reasoning", "uncertainty calibration", "error detection"],
     "practice": ["worked problems", "counterexamples", "held-out reasoning tests"]},
    {"curriculum_id": "programming", "brain_id": "ac_code", "domain": "software and programming",
     "objectives": ["read and explain code", "debugging", "testing", "architecture and secure coding"],
     "practice": ["unit-test tasks", "bug diagnosis", "sandbox project review"]},
    {"curriculum_id": "research", "brain_id": "ac_research", "domain": "research and knowledge",
     "objectives": ["source discovery", "provenance tracking", "claim verification", "conflict analysis"],
     "practice": ["source comparison", "citation audits", "evidence synthesis"]},
    {"curriculum_id": "science", "brain_id": "ac_science", "domain": "science, mathematics and engineering",
     "objectives": ["mathematical problem solving", "scientific method", "dimensional analysis", "engineering validation"],
     "practice": ["proof exercises", "simulation review", "measurement problems"]},
    {"curriculum_id": "vision", "brain_id": "ac_vision", "domain": "vision and document understanding",
     "objectives": ["visual description", "diagram interpretation", "OCR quality assessment", "uncertainty reporting"],
     "practice": ["labelled evaluation sets", "diagram questions", "OCR comparisons"]},
    {"curriculum_id": "media", "brain_id": "ac_media", "domain": "audio, video and creative media",
     "objectives": ["media understanding", "editing workflows", "quality evaluation", "rights awareness"],
     "practice": ["metadata analysis", "creative briefs", "quality rubrics"]},
    {"curriculum_id": "language", "brain_id": "ac_language", "domain": "languages and communication",
     "objectives": ["translation accuracy", "multilingual comprehension", "style control", "terminology consistency"],
     "practice": ["parallel-text review", "terminology tests", "blind translation evaluation"]},
    {"curriculum_id": "strategy", "brain_id": "ac_strategy", "domain": "business and strategy",
     "objectives": ["decision analysis", "risk assessment", "resource planning", "scenario comparison"],
     "practice": ["case studies", "scenario planning", "assumption audits"]},
    {"curriculum_id": "execution", "brain_id": "ac_execution", "domain": "execution and automation",
     "objectives": ["task decomposition", "permission boundaries", "reproducibility", "verification"],
     "practice": ["dry-run workflows", "test-plan design", "sandbox policy reviews"]},
    {"curriculum_id": "memory", "brain_id": "ac_memory", "domain": "memory and knowledge retrieval",
     "objectives": ["retrieval relevance", "source attribution", "retention discipline", "staleness detection"],
     "practice": ["retrieval benchmarks", "provenance audits", "forgetting and update scenarios"]},
    {"curriculum_id": "health", "brain_id": "ac_science", "domain": "health and biomedical knowledge",
     "objectives": ["evidence grading", "medical terminology", "risk communication", "clinical boundary awareness"],
     "practice": ["guideline comparison", "evidence extraction", "safety scenario review"]},
    {"curriculum_id": "law", "brain_id": "ac_research", "domain": "law and governance",
     "objectives": ["jurisdiction awareness", "primary-source research", "legal citation checks", "uncertainty disclosure"],
     "practice": ["statute retrieval", "case comparison", "jurisdiction scenarios"]},
    {"curriculum_id": "agriculture", "brain_id": "ac_science", "domain": "agriculture and environment",
     "objectives": ["agronomy fundamentals", "environmental reasoning", "local-context awareness", "sustainability analysis"],
     "practice": ["field scenarios", "data interpretation", "resource planning"]},
    {"curriculum_id": "design", "brain_id": "ac_media", "domain": "design, architecture and 3D",
     "objectives": ["visual communication", "spatial reasoning", "design constraints", "iteration critique"],
     "practice": ["design briefs", "constraint checks", "critique exercises"]},
    {"curriculum_id": "economics", "brain_id": "ac_strategy", "domain": "economics and finance",
     "objectives": ["quantitative literacy", "assumption disclosure", "scenario analysis", "risk communication"],
     "practice": ["data interpretation", "case studies", "sensitivity analysis"]},
)

CURRICULUM_BY_ID = {item["curriculum_id"]: item for item in CURRICULA}


class TrainingStore:
    """Persists training plans and evaluations. It never launches a trainer or modifies weights."""

    def __init__(self, database_path: str):
        self._uri = database_path == ":memory:"
        self.database_path = (f"file:ac_training_{uuid.uuid4().hex}?mode=memory&cache=shared"
                              if self._uri else str(Path(database_path).expanduser()))
        if not self._uri:
            Path(self.database_path).parent.mkdir(parents=True, exist_ok=True)
        self._keeper = self._connect() if self._uri else None
        self._initialize()

    def _connect(self):
        db = sqlite3.connect(self.database_path, timeout=10, uri=self._uri)
        db.row_factory = sqlite3.Row
        return db

    def _initialize(self):
        with closing(self._connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS training_runs (
                run_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                curriculum_id TEXT NOT NULL, brain_id TEXT NOT NULL, learning_mode TEXT NOT NULL,
                trigger_mode TEXT NOT NULL, autonomy TEXT NOT NULL, status TEXT NOT NULL,
                execution_status TEXT NOT NULL, dataset_manifest_json TEXT NOT NULL,
                evaluation_json TEXT, notes TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_training_created ON training_runs(created_at)")

    def curricula(self):
        return [dict(item, learning_mode="hybrid", autonomy="sandbox") for item in CURRICULA]

    def create_run(self, *, curriculum_id: str, trigger_mode: str = "manual",
                   dataset_manifest: list | None = None, notes: str = ""):
        if curriculum_id not in CURRICULUM_BY_ID:
            raise ValueError("unknown_curriculum")
        if trigger_mode not in {"manual", "scheduled", "continuous"}:
            raise ValueError("invalid_trigger_mode")
        if dataset_manifest is None:
            dataset_manifest = []
        if not isinstance(dataset_manifest, list) or len(dataset_manifest) > 100:
            raise ValueError("dataset_manifest_must_be_a_list_of_at_most_100_items")
        for item in dataset_manifest:
            if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip()
                    for k in ("name", "source", "license_id")):
                raise ValueError("each_dataset_requires_name_source_and_license_id")
        if not isinstance(notes, str) or len(notes) > 2000:
            raise ValueError("invalid_training_notes")
        curriculum = CURRICULUM_BY_ID[curriculum_id]
        run_id, now = str(uuid.uuid4()), utc_now()
        with closing(self._connect()) as db, db:
            db.execute("""INSERT INTO training_runs
                (run_id, created_at, updated_at, curriculum_id, brain_id, learning_mode,
                 trigger_mode, autonomy, status, execution_status, dataset_manifest_json,
                 evaluation_json, notes)
                VALUES (?, ?, ?, ?, ?, 'hybrid', ?, 'sandbox', 'sandbox_queued',
                        'trainer_runtime_not_configured', ?, NULL, ?)""",
                (run_id, now, now, curriculum_id, curriculum["brain_id"], trigger_mode,
                 json.dumps(dataset_manifest, ensure_ascii=False), notes))
        return self.get_run(run_id)

    def get_run(self, run_id: str):
        with closing(self._connect()) as db:
            row = db.execute("SELECT * FROM training_runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._decode(row) if row else None

    def list_runs(self, limit: int = 50):
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit_must_be_between_1_and_100")
        with closing(self._connect()) as db:
            rows = db.execute("SELECT * FROM training_runs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [self._decode(row) for row in rows]

    def record_evaluation(self, run_id: str, *, metrics: dict, held_out: bool):
        if not isinstance(held_out, bool) or not held_out:
            raise ValueError("evaluation_must_use_held_out_data")
        if not isinstance(metrics, dict) or not metrics:
            raise ValueError("evaluation_metrics_required")
        if any(not isinstance(k, str) or not k.strip() or isinstance(v, bool)
               or not isinstance(v, (int, float)) or not 0 <= v <= 1 for k, v in metrics.items()):
            raise ValueError("metrics_must_be_named_scores_between_0_and_1")
        with closing(self._connect()) as db, db:
            row = db.execute("SELECT status FROM training_runs WHERE run_id = ?", (run_id,)).fetchone()
            if row is None:
                raise KeyError(run_id)
            if row["status"] not in {"sandbox_queued", "evaluation_recorded"}:
                raise ValueError("training_run_not_evaluable")
            threshold_met = all(float(value) >= 0.8 for value in metrics.values())
            evaluation = {
                "metrics": {k: float(v) for k, v in metrics.items()},
                "held_out_claimed_by_caller": True,
                "threshold": 0.8,
                "score_threshold_met": threshold_met,
                "passed": False,
                "eligible_for_human_review": False,
                "verification_status": "self_reported_unverified",
                "weights_updated": False,
            }
            db.execute("""UPDATE training_runs SET status = 'evaluation_recorded',
                execution_status = 'evaluation_only_no_training_runtime',
                evaluation_json = ?, updated_at = ? WHERE run_id = ?""",
                (json.dumps(evaluation, ensure_ascii=False), utc_now(), run_id))
        return self.get_run(run_id)

    @staticmethod
    def _decode(row):
        return {"run_id": row["run_id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
                "curriculum_id": row["curriculum_id"], "brain_id": row["brain_id"],
                "learning_mode": row["learning_mode"], "trigger_mode": row["trigger_mode"],
                "autonomy": row["autonomy"], "status": row["status"],
                "execution_status": row["execution_status"],
                "dataset_manifest": json.loads(row["dataset_manifest_json"]),
                "evaluation": json.loads(row["evaluation_json"]) if row["evaluation_json"] else None,
                "notes": row["notes"]}


def training_policy():
    return dict(TRAINING_POLICY)
