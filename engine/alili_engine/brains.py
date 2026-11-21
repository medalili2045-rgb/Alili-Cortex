"""Logical specialist brain contracts, registry, and deterministic routing."""

from dataclasses import asdict, dataclass
from typing import Literal

BrainStatus = Literal["planned", "experimental", "available", "degraded", "disabled"]


@dataclass(frozen=True)
class BrainManifest:
    brain_id: str
    name: str
    version: str
    domains: tuple[str, ...]
    task_types: tuple[str, ...]
    status: BrainStatus = "planned"
    runtime: str = "not_configured"
    license_id: str = "not_applicable"
    min_ram_mb: int = 0
    permissions: tuple[str, ...] = ()

    def __post_init__(self):
        if not self.brain_id or not self.version:
            raise ValueError("brain_id and version are required")
        if self.min_ram_mb < 0:
            raise ValueError("min_ram_mb cannot be negative")

    def to_dict(self) -> dict:
        value = asdict(self)
        for key in ("domains", "task_types", "permissions"):
            value[key] = list(value[key])
        return value


class BrainRegistry:
    """Registry of logical brains; registration does not imply runtime availability."""

    def __init__(self, brains: tuple[BrainManifest, ...] | None = None):
        entries = brains if brains is not None else self.default_brains()
        self._brains = {}
        for brain in entries:
            self.register(brain)

    @staticmethod
    def default_brains() -> tuple[BrainManifest, ...]:
        return (
            BrainManifest("ac_reasoning", "AC Reasoning", "1.0.0",
                          ("reasoning", "logic"), ("reasoning", "analysis")),
            BrainManifest("ac_code", "AC Code", "1.0.0",
                          ("software", "programming"), ("code", "debugging")),
            BrainManifest("ac_research", "AC Research", "1.0.0",
                          ("research", "knowledge"), ("research", "source_review")),
            BrainManifest("ac_science", "AC Science", "1.0.0",
                          ("science", "mathematics", "engineering"), ("science", "math")),
            BrainManifest("ac_vision", "AC Vision", "1.0.0",
                          ("vision", "ocr"), ("image_analysis", "ocr")),
            BrainManifest("ac_media", "AC Media", "1.0.0",
                          ("audio", "video", "media"), ("audio", "video", "media_generation")),
            BrainManifest("ac_language", "AC Language", "1.0.0",
                          ("language", "translation"), ("translation", "language")),
            BrainManifest("ac_strategy", "AC Strategy", "1.0.0",
                          ("strategy", "business"), ("planning", "business_analysis")),
            BrainManifest("ac_execution", "AC Execution", "1.0.0",
                          ("execution", "tools"), ("software_execution", "tool_execution"),
                          permissions=("sandbox_execution",)),
            BrainManifest("ac_memory", "AC Memory", "1.0.0",
                          ("memory", "retrieval"), ("memory_retrieval",)),
        )

    def register(self, brain: BrainManifest) -> None:
        if brain.brain_id in self._brains:
            raise ValueError(f"Duplicate brain ID: {brain.brain_id}")
        self._brains[brain.brain_id] = brain

    def get(self, brain_id: str) -> BrainManifest | None:
        return self._brains.get(brain_id)

    def all(self) -> list[dict]:
        return [brain.to_dict() for brain in self._brains.values()]


@dataclass(frozen=True)
class RoutingDecision:
    task_type: str
    brain_id: str | None
    status: str
    executable: bool
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class BrainRouter:
    """Selects a logical specialist but never executes a model or tool."""

    _task_map = {
        "reasoning": "ac_reasoning",
        "analysis": "ac_reasoning",
        "code": "ac_code",
        "debugging": "ac_code",
        "research": "ac_research",
        "source_review": "ac_research",
        "science": "ac_science",
        "math": "ac_science",
        "image_analysis": "ac_vision",
        "ocr": "ac_vision",
        "audio": "ac_media",
        "video": "ac_media",
        "media_generation": "ac_media",
        "translation": "ac_language",
        "language": "ac_language",
        "planning": "ac_strategy",
        "business_analysis": "ac_strategy",
        "software_execution": "ac_execution",
        "tool_execution": "ac_execution",
        "memory_retrieval": "ac_memory",
    }

    def __init__(self, registry: BrainRegistry):
        self.registry = registry

    def route(self, task_type: str) -> RoutingDecision:
        normalized = (task_type or "").strip().lower()
        brain_id = self._task_map.get(normalized)
        if brain_id is None:
            return RoutingDecision(normalized, None, "unmatched", False, "no_brain_matches_task_type")
        brain = self.registry.get(brain_id)
        if brain is None:
            return RoutingDecision(normalized, brain_id, "unregistered", False, "brain_not_registered")
        executable = brain.status == "available"
        reason = "brain_available" if executable else "brain_registered_but_not_operational"
        return RoutingDecision(normalized, brain_id, brain.status, executable, reason)
