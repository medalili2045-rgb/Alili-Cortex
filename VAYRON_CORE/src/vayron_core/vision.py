"""Optional SigLIP 2 image encoder and trainable Vayron visual projector.

The pretrained encoder is a replaceable third-party component. Only the projector
is trainable by default; downloaded weights are never relabeled as Vayron weights.
"""
from __future__ import annotations

from typing import Sequence

try:
    import torch
    from torch import nn
    import torch.nn.functional as F
except ImportError as exc:  # pragma: no cover - optional dependency
    raise ImportError("Vision support requires PyTorch; install the 'train' extra") from exc


class VayronVisionProjector(nn.Module):
    """Pool patch features to a bounded token count and map them to Vayron width."""

    def __init__(self, input_dim: int, output_dim: int, max_visual_tokens: int = 16) -> None:
        super().__init__()
        if input_dim < 1 or output_dim < 1 or max_visual_tokens < 1:
            raise ValueError("vision dimensions and max_visual_tokens must be positive")
        self.max_visual_tokens = max_visual_tokens
        self.projection = nn.Sequential(
            nn.Linear(input_dim, output_dim),
            nn.LayerNorm(output_dim),
        )

    def forward(self, patch_features: torch.Tensor) -> torch.Tensor:
        if not isinstance(patch_features, torch.Tensor) or patch_features.ndim != 3:
            raise ValueError("patch_features must have shape [batch, patches, channels]")
        if patch_features.shape[0] < 1 or patch_features.shape[1] < 1:
            raise ValueError("patch_features batch and patch dimensions cannot be empty")
        if not torch.is_floating_point(patch_features):
            raise TypeError("patch_features must be floating point")
        # Adaptive pooling bounds visual context even for high-resolution encoders.
        pooled = F.adaptive_avg_pool1d(
            patch_features.transpose(1, 2), self.max_visual_tokens
        ).transpose(1, 2)
        return self.projection(pooled)


class Siglip2VisionAdapter(nn.Module):
    """Frozen SigLIP 2 Base encoder with a trainable Vayron-width projector.

    Model files are fetched only when this adapter is explicitly constructed.
    Set local_files_only=True to prohibit network access.
    """

    MODEL_ID = "google/siglip2-base-patch16-224"

    def __init__(
        self,
        output_dim: int,
        *,
        model_id: str = MODEL_ID,
        max_visual_tokens: int = 16,
        device: str | torch.device | None = None,
        local_files_only: bool = False,
    ) -> None:
        super().__init__()
        try:
            from transformers import AutoModel, AutoProcessor
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "Install vision dependencies with: pip install -e '.[vision]'"
            ) from exc

        self.processor = AutoProcessor.from_pretrained(
            model_id, local_files_only=local_files_only
        )
        loaded = AutoModel.from_pretrained(
            model_id, use_safetensors=True, local_files_only=local_files_only
        )
        if not hasattr(loaded, "vision_model"):
            raise RuntimeError("Selected model does not expose a vision_model")
        self.encoder = loaded.vision_model
        input_dim = int(self.encoder.config.hidden_size)
        self.projector = VayronVisionProjector(
            input_dim, output_dim, max_visual_tokens=max_visual_tokens
        )
        for parameter in self.encoder.parameters():
            parameter.requires_grad_(False)
        self.device_name = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )
        self.to(self.device_name)
        self.encoder.eval()

    def train(self, mode: bool = True):
        # Keep the pretrained encoder deterministic/frozen while training projector.
        super().train(mode)
        self.encoder.eval()
        return self

    def forward(self, images: Sequence[object]) -> torch.Tensor:
        if not images:
            raise ValueError("images cannot be empty")
        batch = self.processor(images=list(images), return_tensors="pt")
        pixel_values = batch["pixel_values"].to(self.device_name)
        with torch.no_grad():
            features = self.encoder(pixel_values=pixel_values).last_hidden_state
        return self.projector(features)
