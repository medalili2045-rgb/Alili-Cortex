"""Local model contracts; no external provider or trained weights bundled."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ModelDescriptor:
    name: str
    version: str
    architecture: str
    weights_path: str
    license_note: str


class LocalModelAdapter(Protocol):
    descriptor: ModelDescriptor

    def generate(self, prompt: str, *, max_new_tokens: int = 512) -> str: ...


class ModelRuntime:
    """Registry for locally executed models with explicit readiness reporting."""

    def __init__(self) -> None:
        self._models: dict[str, LocalModelAdapter] = {}

    def register(self, adapter: LocalModelAdapter) -> None:
        name = adapter.descriptor.name.strip()
        if not name:
            raise ValueError("Model name cannot be empty")
        if name in self._models:
            raise ValueError(f"Model already registered: {name}")
        if not adapter.descriptor.license_note.strip():
            raise ValueError("Model license/provenance note is required")
        self._models[name] = adapter

    def generate(self, model_name: str, prompt: str, *, max_new_tokens: int = 512) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if not 1 <= max_new_tokens <= 8192:
            raise ValueError("max_new_tokens must be between 1 and 8192")
        try:
            adapter = self._models[model_name]
        except KeyError as exc:
            raise LookupError(f"Local model is not registered: {model_name}") from exc
        return adapter.generate(prompt, max_new_tokens=max_new_tokens)

    def status(self) -> dict:
        return {
            "execution_mode": "local_only",
            "model_count": len(self._models),
            "models": [
                {
                    "name": model.descriptor.name,
                    "version": model.descriptor.version,
                    "architecture": model.descriptor.architecture,
                    "weights_path": model.descriptor.weights_path,
                    "license_note": model.descriptor.license_note,
                }
                for model in self._models.values()
            ],
        }
