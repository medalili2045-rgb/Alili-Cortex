"""VAYRON_CORE: independent, provider-agnostic AI system foundation."""

from .engine import VayronEngine
from .memory import MemoryStore
from .registry import CapabilityRegistry, Capability
from .heads import HeadRouter, HeadSpec, DEFAULT_HEADS
from .planner import TaskPlanner, TaskPlan
from .verification import ResultVerifier, VerificationReport
from .network import VayronNetwork, NetworkTrace
from .learning import LearningJournal, LearningCandidate

__all__ = [
    "VayronEngine", "MemoryStore", "CapabilityRegistry", "Capability",
    "HeadRouter", "HeadSpec", "DEFAULT_HEADS", "TaskPlanner", "TaskPlan",
    "ResultVerifier", "VerificationReport", "VayronNetwork", "NetworkTrace",
    "LearningJournal", "LearningCandidate",
]
__version__ = "0.2.0"
