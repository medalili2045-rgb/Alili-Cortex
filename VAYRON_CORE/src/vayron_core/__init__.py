"""VAYRON_CORE: independent, provider-agnostic AI system foundation."""

from .engine import VayronEngine
from .memory import MemoryStore
from .registry import CapabilityRegistry, Capability
from .heads import HeadRouter, HeadSpec, DEFAULT_HEADS
from .planner import TaskPlanner, TaskPlan
from .verification import ResultVerifier, VerificationReport
from .network import VayronNetwork, NetworkTrace
from .learning import LearningJournal, LearningCandidate
from .model_runtime import ModelRuntime, ModelDescriptor, LocalModelAdapter
from .tokenizer import VayronByteTokenizer, TokenizerConfig
from .assistant import VayronAssistant, AssistantReply

__all__ = [
    "VayronEngine", "MemoryStore", "CapabilityRegistry", "Capability",
    "HeadRouter", "HeadSpec", "DEFAULT_HEADS", "TaskPlanner", "TaskPlan",
    "ResultVerifier", "VerificationReport", "VayronNetwork", "NetworkTrace",
    "LearningJournal", "LearningCandidate", "ModelRuntime", "ModelDescriptor",
    "LocalModelAdapter", "VayronByteTokenizer", "TokenizerConfig",
    "VayronAssistant", "AssistantReply",
]
__version__ = "0.4.0"
