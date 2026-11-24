"""PyTorch checkpoint adapter for local-only Vayron inference."""
from pathlib import Path

try:
    import torch
except ImportError as exc:  # pragma: no cover
    raise ImportError("Install Vayron training extras: pip install -e '.[train]'") from exc

from .model_runtime import ModelDescriptor
from .neural import VayronLanguageModel
from .tokenizer import VayronByteTokenizer
from .training import load_checkpoint


class TorchCheckpointAdapter:
    def __init__(self, checkpoint_path: str | Path, *, device: str = "cpu") -> None:
        self.checkpoint_path = Path(checkpoint_path)
        if not self.checkpoint_path.is_file():
            raise FileNotFoundError(self.checkpoint_path)
        metadata = torch.load(self.checkpoint_path, map_location=device, weights_only=True)
        provenance = metadata.get("data_provenance", {})
        license_note = str(provenance.get("license_note", "")).strip()
        if not license_note:
            raise ValueError("Checkpoint is missing training-data license provenance")
        config = metadata.get("model_config", {})
        self.model: VayronLanguageModel = load_checkpoint(self.checkpoint_path, device=device)
        self.tokenizer = VayronByteTokenizer()
        self.device = torch.device(device)
        self.descriptor = ModelDescriptor(
            name="vayron-local",
            version="0.4.0",
            architecture=f"VayronDecoder(d_model={config.get('d_model')}, layers={config.get('n_layers')})",
            weights_path=str(self.checkpoint_path),
            license_note=license_note,
        )

    def generate(self, prompt: str, *, max_new_tokens: int = 512) -> str:
        if not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        if not 1 <= max_new_tokens <= 8192:
            raise ValueError("max_new_tokens must be between 1 and 8192")
        token_ids = self.tokenizer.encode(prompt)
        input_ids = torch.tensor([token_ids], dtype=torch.long, device=self.device)
        with torch.no_grad():
            output = self.model.generate(input_ids, max_new_tokens=max_new_tokens)
        generated = output[0, len(token_ids):].tolist()
        return self.tokenizer.decode(generated)
