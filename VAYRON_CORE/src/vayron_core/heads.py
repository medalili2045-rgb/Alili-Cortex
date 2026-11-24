"""Specialist head definitions for the original Vayron architecture.

These are routing profiles, not individually trained neural networks.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class HeadSpec:
    name: str
    purpose: str
    keywords: tuple[str, ...]


DEFAULT_HEADS: tuple[HeadSpec, ...] = (
    HeadSpec("THINK_yzn", "general analysis and task framing", ("think", "explain", "why", "حلل", "اشرح", "لماذا")),
    HeadSpec("REASON_yzn", "structured reasoning and problem solving", ("reason", "logic", "solve", "استنتج", "منطق")),
    HeadSpec("SEARCH_yzn", "research and source discovery", ("search", "find", "بحث", "ابحث", "مصادر")),
    HeadSpec("FLASH_yzn", "fast response and concise task handling", ("quick", "fast", "brief", "سريع", "باختصار")),
    HeadSpec("LEARN_yzn", "learning plans and knowledge acquisition", ("learn", "study", "train", "تعلم", "ادرس", "تدرب")),
    HeadSpec("MEMORY_yzn", "memory retrieval and knowledge organization", ("remember", "memory", "recall", "تذكر", "ذاكرة", "استرجع")),
    HeadSpec("CODE_yzn", "software engineering and code", ("code", "python", "javascript", "برمج", "كود", "شفرة")),
    HeadSpec("BUILD_yzn", "application and project construction", ("build", "create app", "project", "أنشئ", "تطبيق", "مشروع")),
    HeadSpec("VISION_yzn", "image and visual understanding", ("image", "picture", "photo", "صورة", "بصري")),
    HeadSpec("VERIFY_yzn", "testing, evidence and validation", ("verify", "test", "check", "تحقق", "اختبر", "افحص")),
    HeadSpec("EVOLVE_yzn", "measured improvement proposals", ("improve", "optimize", "evolve", "طور", "حسن", "تحسين")),
    HeadSpec("KNOW_yzn", "knowledge organization and explanation", ("knowledge", "concept", "معرفة", "مفهوم")),
    HeadSpec("SKILL_yzn", "reusable skill and workflow design", ("skill", "workflow", "مهارة", "سير عمل")),
    HeadSpec("RESEARCH_yzn", "deep technical research", ("paper", "documentation", "benchmark", "ورقة", "توثيق", "معيار")),
    HeadSpec("SELFTEST_yzn", "self diagnostics and regression checks", ("selftest", "diagnostic", "regression", "تشخيص", "فحص ذاتي")),
    HeadSpec("GUARD_yzn", "safety, permissions and policy checks", ("safe", "security", "permission", "أمان", "حماية", "صلاحية")),
    HeadSpec("TOOLMAKER_yzn", "tool and adapter design", ("tool", "adapter", "integration", "أداة", "تكامل")),
    HeadSpec("CODEAUDIT_yzn", "code review and security audit", ("audit", "review code", "vulnerability", "راجع الكود", "ثغرة", "تدقيق")),
)


class HeadRouter:
    """Transparent keyword router; intentionally not represented as an LLM."""

    def __init__(self, heads: tuple[HeadSpec, ...] = DEFAULT_HEADS) -> None:
        names = [head.name for head in heads]
        if len(names) != len(set(names)):
            raise ValueError("Head names must be unique")
        if any(not name.endswith("_yzn") for name in names):
            raise ValueError("Every specialist head name must end with _yzn")
        self._heads = heads

    def all_heads(self) -> tuple[HeadSpec, ...]:
        return self._heads

    def route(self, text: str) -> HeadSpec:
        normalized = text.casefold()
        scored = [
            (sum(1 for word in head.keywords if word.casefold() in normalized), -index, head)
            for index, head in enumerate(self._heads)
        ]
        score, _, selected = max(scored, key=lambda item: (item[0], item[1]))
        if score == 0:
            return next(head for head in self._heads if head.name == "THINK_yzn")
        return selected
