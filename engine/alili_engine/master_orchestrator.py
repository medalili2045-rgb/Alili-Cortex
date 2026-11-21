"""AC Master: independent specialist planning and coordination contracts.

This module creates bounded, reviewable delegation plans. It does not invoke
models, execute tools, or claim that a registered brain has a live runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class BrainAssignment:
    brain_id: str
    role: str
    objective: str
    dependencies: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "brain_id": self.brain_id,
            "role": self.role,
            "objective": self.objective,
            "dependencies": list(self.dependencies),
            "execution_status": "not_dispatched",
            "isolated_context": True,
            "shared_mutable_context": False,
        }


class ACMasterOrchestrator:
    """Builds multi-specialist plans while keeping each brain autonomous."""

    VERSION = "1.0.0"
    MAX_BRAINS = 8
    MAX_OBJECTIVE_CHARS = 16_000

    _signals = {
        "ac_code": ("code", "coding", "program", "debug", "software", "api", "برمج", "كود", "شفرة", "تصحيح", "تطبيق"),
        "ac_research": ("research", "search", "sources", "references", "paper", "study", "بحث", "ابحث", "مصادر", "مراجع", "دراسة"),
        "ac_science": ("science", "math", "physics", "chemistry", "biology", "engineering", "رياضيات", "فيزياء", "كيمياء", "علوم", "هندسة", "أحياء"),
        "ac_vision": ("image", "photo", "picture", "vision", "ocr", "صورة", "صور", "بصري", "استخراج النص"),
        "ac_media": ("video", "audio", "sound", "music", "animation", "فيديو", "صوت", "موسيقى", "تحريك"),
        "ac_language": ("translate", "translation", "language", "write", "rewrite", "ترجم", "ترجمة", "لغة", "اكتب", "صياغة"),
        "ac_strategy": ("strategy", "business", "market", "roadmap", "plan", "تخطيط", "استراتيجية", "مشروع", "أعمال", "سوق"),
        "ac_memory": ("remember", "recall", "history", "memory", "تذكر", "ذاكرة", "سابق", "الماضي"),
        "ac_execution": ("execute", "run", "deploy", "test", "build", "تشغيل", "نفذ", "اختبر", "انشر", "بناء"),
    }

    _labels = {
        "ac_reasoning": "التحليل المنطقي ومراجعة الترابط",
        "ac_code": "التصميم البرمجي والتنفيذ التقني",
        "ac_research": "البحث وجمع الأدلة والمصادر",
        "ac_science": "التحليل العلمي والرياضي",
        "ac_vision": "فهم الصور والوثائق المرئية",
        "ac_media": "الصوت والفيديو والوسائط",
        "ac_language": "اللغة والتحرير والترجمة",
        "ac_strategy": "الاستراتيجية والتخطيط",
        "ac_memory": "استرجاع المعرفة والسياق",
        "ac_execution": "التنفيذ والاختبار ضمن الصلاحيات",
    }

    def __init__(self, registry):
        self.registry = registry

    def plan(self, objective: str, *, requested_brains=None, max_brains: int = 6) -> dict:
        if not isinstance(objective, str) or not objective.strip() or len(objective) > self.MAX_OBJECTIVE_CHARS:
            raise ValueError("invalid_master_objective")
        if isinstance(max_brains, bool) or not isinstance(max_brains, int) or not 1 <= max_brains <= self.MAX_BRAINS:
            raise ValueError("max_brains_out_of_range")
        requested = requested_brains or []
        if not isinstance(requested, list) or len(requested) > self.MAX_BRAINS:
            raise ValueError("invalid_requested_brains")
        if any(not isinstance(value, str) or not value.strip() for value in requested):
            raise ValueError("invalid_requested_brains")
        registered = {item["brain_id"] for item in self.registry.all()}
        unknown = sorted(set(requested) - registered)
        if unknown:
            raise ValueError("unknown_brain:" + ",".join(unknown))
        text = objective.casefold()
        scores = {}
        for brain_id, signals in self._signals.items():
            score = sum(1 for signal in signals if signal.casefold() in text)
            if score and self.registry.get(brain_id):
                scores[brain_id] = score
        selected = list(dict.fromkeys(requested))
        for brain_id, _score in sorted(scores.items(), key=lambda pair: (-pair[1], pair[0])):
            if brain_id not in selected and len(selected) < max_brains:
                selected.append(brain_id)
        if not selected:
            selected = ["ac_reasoning"] if self.registry.get("ac_reasoning") else []
        elif "ac_reasoning" not in selected and len(selected) < max_brains and self.registry.get("ac_reasoning"):
            selected.append("ac_reasoning")

        manifests = {item["brain_id"]: item for item in self.registry.all()}
        assignments = []
        for brain_id in selected:
            assignments.append(BrainAssignment(
                brain_id=brain_id,
                role="integration_and_critical_review" if brain_id == "ac_reasoning" else "independent_specialist",
                objective=f"{self._labels.get(brain_id, 'المهمة المتخصصة')}: {objective.strip()}",
            ).to_dict())
        for assignment in assignments:
            manifest = manifests[assignment["brain_id"]]
            assignment["brain_status"] = manifest["status"]
            assignment["runtime"] = manifest["runtime"]
            assignment["dispatchable"] = manifest["status"] == "available" and manifest["runtime"] != "not_configured"

        return {
            "plan_id": "ac-plan-" + uuid4().hex[:20],
            "master_version": self.VERSION,
            "coordinator": "AC Master",
            "objective": objective.strip(),
            "mode": "independent_specialists_with_central_coordination",
            "parallelism": "eligible_assignments_may_run_in_parallel",
            "max_brains": max_brains,
            "assignments": assignments,
            "quality_gate": {
                "reviewer": "ac_reasoning",
                "checks": ["evidence_and_provenance", "internal_consistency", "conflict_detection",
                           "policy_and_permission_boundaries", "test_or_validation_results"],
                "finalization_requires_review": True,
            },
            "isolation": {
                "separate_assignment_contexts": True,
                "shared_mutable_context": False,
                "exchange_via_versioned_artifacts": True,
                "specialists_may_report_disagreement": True,
            },
            "execution": {
                "dispatched": False,
                "status": "planning_only",
                "reason": "specialist_runtimes_and_dispatch_adapters_are_not_yet_connected",
            },
            "learning": {
                "automatic_weight_training": False,
                "knowledge_requires_provenance_and_review": True,
            },
        }
