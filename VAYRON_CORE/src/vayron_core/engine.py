"""Central request orchestrator with safe, deterministic defaults."""

from typing import Any
from .registry import CapabilityRegistry
from .memory import MemoryStore


class VayronEngine:
    def __init__(
        self,
        registry: CapabilityRegistry | None = None,
        memory: MemoryStore | None = None,
    ) -> None:
        self.registry = registry or CapabilityRegistry()
        self.memory = memory

    def status(self) -> dict[str, Any]:
        return {
            "name": "Alili Vayron",
            "core": "VAYRON_CORE",
            "version": "0.1.0",
            "ready": True,
            "model_loaded": False,
            "external_api_required": False,
            "capabilities": list(self.registry.names()),
        }

    def execute_capability(self, name: str, payload: dict[str, Any]) -> Any:
        """Run only a capability explicitly registered by the application."""
        capability = self.registry.get(name)
        return capability.handler(payload)

    def respond(self, message: str) -> str:
        """Honest bootstrap response until an original language model is integrated."""
        prompt = message.strip()
        if not prompt:
            raise ValueError("Message cannot be empty")
        return (
            "VAYRON_CORE is running in foundation mode. "
            "The original language model is not integrated yet. "
            "Your message was received; connect a tested local model adapter "
            "to enable generated reasoning and conversation."
        )
