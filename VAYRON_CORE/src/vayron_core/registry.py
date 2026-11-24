"""Provider-neutral capability registration."""

from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Capability:
    name: str
    handler: Callable[[dict[str, Any]], Any]
    description: str = ""


class CapabilityRegistry:
    """Explicit registry; nothing is loaded or executed implicitly."""

    def __init__(self) -> None:
        self._capabilities: dict[str, Capability] = {}

    def register(self, capability: Capability) -> None:
        key = capability.name.strip().lower()
        if not key:
            raise ValueError("Capability name cannot be empty")
        if key in self._capabilities:
            raise ValueError(f"Capability already registered: {key}")
        self._capabilities[key] = capability

    def get(self, name: str) -> Capability:
        key = name.strip().lower()
        try:
            return self._capabilities[key]
        except KeyError as exc:
            raise LookupError(f"Unknown capability: {key}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._capabilities))
