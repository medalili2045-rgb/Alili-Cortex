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


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 1
    batch_size: int = 4
    learning_rate: float = 3e-4
    max_steps: int = 100
    seed: int = 42
    device: str = "auto"

    def validate(self) -> None:
        if self.epochs < 1 or self.batch_size < 1 or self.max_steps < 1:
            raise ValueError("epochs, batch_size and max_steps must be positive")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")


class TokenBlockDataset(Dataset):
    def __init__(self, token_ids: list[int], block_size: int) -> None:
        if block_size < 2:
            raise ValueError("block_size must be >= 2")
        if len(token_ids) < block_size + 1:
            raise ValueError("training text must contain at least block_size + 1 tokens")
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


def train_text(
    text: str,
    output_dir: str | Path,
    *,
    model_config: VayronModelConfig | None = None,
    training_config: TrainingConfig | None = None,
) -> dict:
    if not text.strip():
        raise ValueError("Training text cannot be empty")
    model_config = model_config or VayronModelConfig()
    training_config = training_config or TrainingConfig()
    model_config.validate()
    training_config.validate()
    random.seed(training_config.seed)
    torch.manual_seed(training_config.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(training_config.seed)

    tokenizer = VayronByteTokenizer()
    tokens = tokenizer.encode(text)
    block_size = model_config.max_seq_len
    dataset = TokenBlockDataset(tokens, block_size)
    loader = DataLoader(dataset, batch_size=training_config.batch_size, shuffle=True)
    device = _device(training_config.device)
    model = VayronLanguageModel(model_config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=training_config.learning_rate)
    losses: list[float] = []
    steps = 0
    model.train()
    for _ in range(training_config.epochs):
        for inputs, targets in loader:
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

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    checkpoint = target / "vayron-small.pt"
    torch.save({
        "model_state_dict": model.state_dict(),
        "model_config": model.config_dict(),
        "tokenizer": tokenizer.to_dict(),
        "training_config": asdict(training_config),
        "steps": steps,
        "final_train_loss": losses[-1],
        "model_origin": "Vayron initialized from random weights; trained only on supplied corpus",
    }, checkpoint)
    report = {
        "checkpoint": str(checkpoint),
        "steps": steps,
        "final_train_loss": losses[-1],
        "device": str(device),
        "trained_from_random_initialization": True,
        "evaluation_loss": None,
        "warning": "Smoke training only: no held-out validation split or quality claim.",
    }
    (target / "training-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def load_checkpoint(path: str | Path, *, device: str = "cpu") -> VayronLanguageModel:
    checkpoint = torch.load(Path(path), map_location=device, weights_only=True)
    config = VayronModelConfig(**checkpoint["model_config"])
    model = VayronLanguageModel(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.to(device)
    model.eval()
    return model
