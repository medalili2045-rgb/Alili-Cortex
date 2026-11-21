"""AC_YZN model family registry. Entries are specifications, not shipped weights."""
from dataclasses import asdict, dataclass
from typing import Literal

ModelStatus = Literal["planned", "experimental", "available", "deprecated"]
WeightsStatus = Literal["not_created", "local_checkpoint_required", "available"]


@dataclass(frozen=True)
class ModelManifest:
    model_id: str
    display_name: str
    family: str
    generation: int
    variant: str
    specialization: tuple[str, ...]
    modalities: tuple[str, ...]
    status: ModelStatus = "planned"
    weights_status: WeightsStatus = "not_created"
    base_checkpoint: str | None = None
    base_license_id: str = "not_selected"
    parameter_count: int | None = None
    strength_tier: str = "unrated"
    benchmark_status: str = "not_evaluated"
    description: str = ""

    def to_dict(self):
        value = asdict(self)
        value["specialization"] = list(value["specialization"])
        value["modalities"] = list(value["modalities"])
        return value


class ModelRegistry:
    """Stable public names for AC models; no model download or inference is performed."""

    def __init__(self, manifests=None):
        entries = manifests if manifests is not None else self.default_models()
        self._models = {}
        for model in entries:
            if model.model_id in self._models:
                raise ValueError(f"duplicate_model_id:{model.model_id}")
            self._models[model.model_id] = model

    @staticmethod
    def default_models():
        return (
            ModelManifest("ac_yzn1", "AC_YZN1", "AC_YZN", 1, "base",
                ("general", "reasoning", "language", "knowledge"), ("text",),
                description="First AC model-family target; local open-weight base checkpoint must be selected and licensed."),
            ModelManifest("ac_yzn1_r", "AC_YZN1-R", "AC_YZN", 1, "reasoning",
                ("reasoning", "logic", "mathematics"), ("text",),
                description="Reasoning specialist candidate derived from the AC_YZN1 family."),
            ModelManifest("ac_yzn1_c", "AC_YZN1-C", "AC_YZN", 1, "code",
                ("programming", "debugging", "software_engineering"), ("text", "code"),
                description="Programming specialist candidate derived from the AC_YZN1 family."),
            ModelManifest("ac_yzn1_sci", "AC_YZN1-SCI", "AC_YZN", 1, "science",
                ("science", "mathematics", "engineering"), ("text",),
                description="Science and engineering specialist candidate."),
            ModelManifest("ac_yzn1_v", "AC_YZN1-V", "AC_YZN", 1, "vision",
                ("vision", "documents", "diagrams"), ("text", "image"),
                description="Vision-capable model candidate; requires a compatible multimodal base checkpoint."),
            ModelManifest("ac_yzn1_mm", "AC_YZN1-MM", "AC_YZN", 1, "multimodal",
                ("general", "vision", "audio"), ("text", "image", "audio"),
                description="Multimodal model candidate; requires a compatible multimodal base checkpoint."),
            ModelManifest("ac_yzn2", "AC_YZN2", "AC_YZN", 2, "next_generation",
                ("general", "multi_domain"), ("text",),
                description="Second-generation target; architecture and benchmark gates are not yet defined."),
        )

    def get(self, model_id: str):
        if not isinstance(model_id, str):
            return None
        return self._models.get(model_id.strip().lower())

    def all(self):
        return [model.to_dict() for model in self._models.values()]

    def family(self):
        return {
            "family_id": "ac_yzn",
            "display_name": "AC_YZN",
            "naming": {
                "generation": "YZN1, YZN2, ...",
                "specialization": {
                    "R": "Reasoning", "C": "Code", "SCI": "Science",
                    "V": "Vision", "MM": "Multimodal"
                },
                "format": "AC_YZN{generation}-{specialization?}-{capacity?}",
                "capacity_suffixes": {
                    "S": "Small", "B": "Base", "L": "Large", "X": "Extra"
                },
                "capacity_rule": "Capacity suffixes are reserved until parameter counts and hardware benchmarks are measured."
            },
            "strength_labels": ["unrated", "standard", "advanced", "high", "frontier"],
            "strength_rule": "Only assign a strength label after published, reproducible held-out benchmark results.",
            "current_weights": "No AC_YZN weights are included or claimed to exist yet."
        }
