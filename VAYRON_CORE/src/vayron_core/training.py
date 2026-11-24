"""Reproducible small-scale causal-LM trainer for Vayron-owned checkpoints."""
from __future__ import annotations

import json
import random
from pathlib import Path
from dataclasses import asdict, dataclass

try:
    import torch
    import torch.nn.functional as F
    from torch.utils.data import DataLoader, Dataset
except ImportError as exc:  # pragma: no cover
    raise ImportError("Install Vayron training extras: pip install -e '.[train]'") from exc

from .neural import VayronLanguageModel, VayronModelConfig
from .tokenizer import VayronByteTokenizer

CHECKPOINT_FORMAT_VERSION = 1


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 1
    batch_size: int = 4
    learning_rate: float = 3e-4
    max_steps: int = 100
    seed: int = 42
    device: str = "auto"
    validation_fraction: float = 0.1

    def validate(self) -> None:
        if self.epochs < 1 or self.batch_size < 1 or self.max_steps < 1:
            raise ValueError("epochs, batch_size and max_steps must be positive")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if not 0.05 <= self.validation_fraction <= 0.4:
            raise ValueError("validation_fraction must be between 0.05 and 0.4")


class TokenBlockDataset(Dataset):
    def __init__(self, token_ids: list[int], block_size: int) -> None:
        if block_size < 2:
            raise ValueError("block_size must be >= 2")
        if len(token_ids) < block_size + 1:
            raise ValueError("text must contain at least block_size + 1 tokens")
        self.tokens = torch.tensor(token_ids, dtype=torch.long)
        self.block_size = block_size
        self.count = len(token_ids) - block_size

    def __len__(self) -> int:
        return self.count

    def __getitem__(self, index: int):
        chunk = self.tokens[index:index + self.block_size + 1]
        return chunk[:-1], chunk[1:]


def _device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    return device


@torch.no_grad()
def _evaluate(model, loader, device) -> float:
    model.eval()
    losses = []
    for inputs, targets in loader:
        inputs, targets = inputs.to(device), targets.to(device)
        logits = model(inputs)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
        if not torch.isfinite(loss):
            raise FloatingPointError("Non-finite validation loss")
        losses.append(float(loss.cpu()))
    if not losses:
        raise ValueError("Validation dataset is empty")
    model.train()
    return sum(losses) / len(losses)


def train_text(
    text: str,
    output_dir: str | Path,
    *,
    source: str,
    license_note: str,
    model_config: VayronModelConfig | None = None,
    training_config: TrainingConfig | None = None,
) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Training text cannot be empty")
    if not isinstance(source, str) or not source.strip() or not isinstance(license_note, str) or not license_note.strip():
        raise ValueError("A source and explicit license/provenance note are required")
    model_config = model_config or VayronModelConfig()
    training_config = training_config or TrainingConfig()
    model_config.validate()
    training_config.validate()
    random.seed(training_config.seed)
    torch.manual_seed(training_config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(training_config.seed)

    tokenizer = VayronByteTokenizer()
    if model_config.vocab_size != tokenizer.vocab_size:
        raise ValueError("Model vocab_size must match the active Vayron tokenizer")
    tokens = tokenizer.encode(text)
    block_size = model_config.max_seq_len
    split = int(len(tokens) * (1.0 - training_config.validation_fraction))
    if split < block_size + 1 or len(tokens) - split < block_size + 1:
        raise ValueError("Corpus is too small for non-overlapping train and validation blocks")
    train_tokens = tokens[:split]
    validation_tokens = tokens[split:]
    train_data = TokenBlockDataset(train_tokens, block_size)
    validation_data = TokenBlockDataset(validation_tokens, block_size)
    train_loader = DataLoader(train_data, batch_size=training_config.batch_size, shuffle=True)
    validation_loader = DataLoader(validation_data, batch_size=training_config.batch_size, shuffle=False)

    device = _device(training_config.device)
    model = VayronLanguageModel(model_config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=training_config.learning_rate)
    losses: list[float] = []
    steps = 0
    model.train()
    for _ in range(training_config.epochs):
        for inputs, targets in train_loader:
            inputs, targets = inputs.to(device), targets.to(device)
            optimizer.zero_grad(set_to_none=True)
            logits = model(inputs)
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
            if not torch.isfinite(loss):
                raise FloatingPointError("Non-finite training loss")
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
            steps += 1
            if steps >= training_config.max_steps:
                break
        if steps >= training_config.max_steps:
            break

    validation_loss = _evaluate(model, validation_loader, device)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    checkpoint = target / "vayron-small.pt"
    checkpoint_payload = {
        "format_version": CHECKPOINT_FORMAT_VERSION,
        "model_state_dict": model.state_dict(),
        "model_config": model.config_dict(),
        "tokenizer": tokenizer.to_dict(),
        "training_config": asdict(training_config),
        "steps": steps,
        "final_train_loss": losses[-1],
        "validation_loss": validation_loss,
        "data_provenance": {"source": source.strip(), "license_note": license_note.strip()},
        "model_origin": "Vayron initialized from random weights; trained only on supplied corpus",
    }
    torch.save(checkpoint_payload, checkpoint)
    report = {
        "checkpoint": str(checkpoint),
        "steps": steps,
        "final_train_loss": losses[-1],
        "validation_loss": validation_loss,
        "device": str(device),
        "trained_from_random_initialization": True,
        "data_provenance": checkpoint_payload["data_provenance"],
        "warning": "Tiny smoke run only; validation on a small split does not establish model quality.",
    }
    (target / "training-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load_checkpoint_bundle(path: str | Path, *, device: str = "cpu") -> tuple[VayronLanguageModel, dict]:
    """Load and validate a Vayron checkpoint and its tokenizer/provenance metadata."""
    checkpoint = torch.load(Path(path), map_location=device, weights_only=True)
    if not isinstance(checkpoint, dict):
        raise ValueError("Checkpoint payload must be a dictionary")
    if checkpoint.get("format_version") != CHECKPOINT_FORMAT_VERSION:
        raise ValueError("Unsupported or missing Vayron checkpoint format version")
    provenance = checkpoint.get("data_provenance")
    if not isinstance(provenance, dict) or not str(provenance.get("source", "")).strip() or not str(provenance.get("license_note", "")).strip():
        raise ValueError("Checkpoint is missing training-data source or license provenance")
    if checkpoint.get("tokenizer") != VayronByteTokenizer().to_dict():
        raise ValueError("Checkpoint tokenizer does not match this Vayron runtime")
    config_data = checkpoint.get("model_config")
    state_dict = checkpoint.get("model_state_dict")
    if not isinstance(config_data, dict) or not isinstance(state_dict, dict):
        raise ValueError("Checkpoint is missing model configuration or weights")
    try:
        config = VayronModelConfig(**config_data)
        if config.vocab_size != VayronByteTokenizer().vocab_size:
            raise ValueError("Checkpoint model vocab_size does not match the active Vayron tokenizer")
        model = VayronLanguageModel(config)
        model.load_state_dict(state_dict, strict=True)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise ValueError("Checkpoint model configuration or weights are invalid") from exc
    model.to(device)
    model.eval()
    return model, checkpoint


def load_checkpoint(path: str | Path, *, device: str = "cpu") -> VayronLanguageModel:
    """Load a validated Vayron checkpoint for local inference."""
    model, _ = load_checkpoint_bundle(path, device=device)
    return model
