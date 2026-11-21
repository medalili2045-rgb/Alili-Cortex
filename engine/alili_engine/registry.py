"""Capability manifests and honest availability states."""

from dataclasses import asdict, dataclass
from typing import Literal

CapabilityStatus = Literal["available", "experimental", "planned", "unavailable"]


@dataclass(frozen=True)
class Capability:
    capability_id: str
    name: str
    version: str
    status: CapabilityStatus
    description: str
    execution_mode: str
    permissions: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        value = asdict(self)
        value["permissions"] = list(self.permissions)
        return value


class CapabilityRegistry:
    def __init__(self, capabilities: tuple[Capability, ...] | None = None):
        entries = capabilities or (
            Capability(
                capability_id="task_planning", name="Task planning", version="0.1.0",
                status="available",
                description="Deterministic local classification and plan generation; does not execute the plan.",
                execution_mode="local_builtin",
            ),
            Capability(
                capability_id="local_language_model", name="Local language model", version="0.2.0",
                status="experimental",
                description="OpenAI-compatible inference through an explicitly configured loopback model runtime; no hosted fallback.",
                execution_mode="local_loopback",
                permissions=("local_model_inference",),
            ),
            Capability(
                capability_id="document_processing", name="Document processing", version="0.1.0",
                status="planned",
                description="Secure extraction and creation for common document formats.",
                execution_mode="local_open_source",
                permissions=("read_user_supplied_files", "create_artifacts"),
            ),
            Capability(
                capability_id="research_search", name="Research and web search", version="0.1.0",
                status="planned",
                description="Protected search adapters with source provenance and citations.",
                execution_mode="local_or_approved_hosted",
                permissions=("network_read",),
            ),
            Capability(
                capability_id="software_execution", name="Software engineering execution", version="0.1.0",
                status="planned",
                description="Isolated project editing, builds, and tests; arbitrary code is not enabled in this foundation.",
                execution_mode="isolated_local_sandbox",
                permissions=("workspace_read", "workspace_write", "run_allowlisted_tools"),
            ),
            Capability(
                capability_id="vision_ocr", name="Vision and OCR", version="0.1.0",
                status="planned",
                description="Image inspection and OCR through locally installed open-source adapters.",
                execution_mode="local_open_source",
                permissions=("read_user_supplied_files",),
            ),
            Capability(
                capability_id="image_audio_video", name="Image, audio, and video production", version="0.1.0",
                status="planned",
                description="Media processing and generation through separately installed compatible tools.",
                execution_mode="local_open_source",
                permissions=("read_user_supplied_files", "create_artifacts"),
            ),
            Capability(
                capability_id="3d_cad", name="3D and CAD", version="0.1.0",
                status="planned",
                description="Blender, FreeCAD, and OpenSCAD integrations after license and runtime validation.",
                execution_mode="local_open_source",
                permissions=("workspace_read", "workspace_write"),
            ),
        )
        self._items = {item.capability_id: item for item in entries}
        if len(self._items) != len(entries):
            raise ValueError("Capability IDs must be unique")

    def get(self, capability_id: str) -> Capability | None:
        return self._items.get(capability_id)

    def all(self) -> list[dict]:
        return [item.to_dict() for item in self._items.values()]
