"""Resumable, provenance-aware causal language-model training for Vayron."""
from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    import torch
    import torch.nn.functional as F
except ImportError as exc:  # pragma: no cover
    raise ImportError("Install Vayron training extras: pip install -e '.[train]'") from exc

from .neural import VayronLanguageModel, VayronModelConfig
from .tokenizer import VayronByteTokenizer

CHECKPOINT_FORMAT_VERSION = 2


@dataclass(frozen=True)
class TrainingConfig:
    epochs: int = 1
    batch_size: int = 4
    learning_rate: float = 3e-4
    max_steps: int = 100
    seed: int = 42
    device: str = "auto"
    validation_fraction: float = 0.1
    gradient_accumulation_steps: int = 1
    checkpoint_every_steps: int = 25
    warmup_steps: int = 0
    min_learning_rate_ratio: float = 0.1

    def validate(self) -> None:
        if self.epochs < 1 or self.batch_size < 1 or self.max_steps < 1:
            raise ValueError("epochs, batch_size and max_steps must be positive")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")
        if not 0.05 <= self.validation_fraction <= 0.4:
            raise ValueError("validation_fraction must be between 0.05 and 0.4")
        if self.gradient_accumulation_steps < 1 or self.checkpoint_every_steps < 1:
            raise ValueError("gradient accumulation and checkpoint interval must be positive")
        if self.warmup_steps < 0 or not 0.0 < self.min_learning_rate_ratio <= 1.0:
            raise ValueError("invalid warmup_steps or min_learning_rate_ratio")


def _device(requested: str) -> torch.device:
    if requested == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device = torch.device(requested)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested but is unavailable")
    return device


def _atomic_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        torch.save(payload, temporary)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _make_payload(
    model, optimizer, scheduler, config, model_config, tokenizer,
    *, global_step, epoch, batch_cursor, permutation, generator,
    best_validation_loss, source, license_note,
):
    return {
        "format_version": CHECKPOINT_FORMAT_VERSION,
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict(),
        "model_config": model_config.__dict__,
        "tokenizer": tokenizer.to_dict(),
        "training_config": asdict(config),
        "global_step": global_step,
        "epoch": epoch,
        "batch_cursor": batch_cursor,
        "permutation": permutation,
        "data_generator_state": generator.get_state(),
        "torch_rng_state": torch.get_rng_state(),
        "cuda_rng_state_all": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
        "best_validation_loss": best_validation_loss,
        "data_provenance": {"source": source, "license_note": license_note},
        "model_origin": "Vayron model initialized from random weights; no external model weights imported.",
    }


@torch.no_grad()
def _evaluate(model, token_ids: list[int], block_size: int, batch_size: int, device) -> float:
    model.eval()
    losses = []
    count = len(token_ids) - block_size
    for start in range(0, count, batch_size):
        indices = range(start, min(start + batch_size, count))
        batch = torch.stack([torch.tensor(token_ids[i:i + block_size + 1], dtype=torch.long) for i in indices])
        inputs, targets = batch[:, :-1].to(device), batch[:, 1:].to(device)
        logits = model(inputs)
        loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
        if not torch.isfinite(loss):
            raise FloatingPointError("Non-finite validation loss")
        losses.append(float(loss.cpu()))
    model.train()
    if not losses:
        raise ValueError("Validation dataset is empty")
    return sum(losses) / len(losses)


def train_text(
    text: str,
    output_dir: str | Path,
    *,
    source: str,
    license_note: str,
    model_config: VayronModelConfig | None = None,
    training_config: TrainingConfig | None = None,
    resume_from: str | Path | None = None,
) -> dict:
    """Train on supplied text; resume_from restores optimizer, schedule, RNG and data cursor.

    max_steps is the target total optimizer-step count, not an additional-step count.
    """
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
    train_tokens, validation_tokens = tokens[:split], tokens[split:]
    train_count = len(train_tokens) - block_size
    if train_count < 1:
        raise ValueError("Training split contains no usable token blocks")

    device = _device(training_config.device)
    model = VayronLanguageModel(model_config).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=training_config.learning_rate)
    total_steps = training_config.max_steps
    warmup = training_config.warmup_steps

    def lr_factor(step: int) -> float:
        if warmup and step < warmup:
            return max((step + 1) / warmup, 1e-8)
        decay_steps = max(total_steps - warmup, 1)
        progress = min(max((step - warmup) / decay_steps, 0.0), 1.0)
        cosine = 0.5 * (1.0 + __import__("math").cos(__import__("math").pi * progress))
        return training_config.min_learning_rate_ratio + (1.0 - training_config.min_learning_rate_ratio) * cosine

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_factor)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(training_config.seed)
    global_step, start_epoch, batch_cursor = 0, 0, 0
    permutation = torch.randperm(train_count, generator=generator)
    best_validation_loss = float("inf")
    history: list[float] = []
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    latest_path = target / "latest-resume.pt"

    if resume_from is not None:
        resume_path = Path(resume_from)
        if not resume_path.is_file():
            raise FileNotFoundError(f"Resume checkpoint not found: {resume_path}")
        saved = torch.load(resume_path, map_location=device, weights_only=True)
        if saved.get("format_version") != CHECKPOINT_FORMAT_VERSION:
            raise ValueError("Resume checkpoint format is unsupported; start a fresh run")
        if saved.get("model_config") != model_config.__dict__:
            raise ValueError("Resume checkpoint model configuration does not match")
        if saved.get("tokenizer") != tokenizer.to_dict():
            raise ValueError("Resume checkpoint tokenizer does not match")
        provenance = saved.get("data_provenance", {})
        if provenance.get("source") != source or provenance.get("license_note") != license_note:
            raise ValueError("Resume corpus provenance must match the original run")
        model.load_state_dict(saved["model_state_dict"], strict=True)
        optimizer.load_state_dict(saved["optimizer_state_dict"])
        scheduler.load_state_dict(saved["scheduler_state_dict"])
        global_step = int(saved["global_step"])
        start_epoch = int(saved["epoch"])
        batch_cursor = int(saved["batch_cursor"])
        permutation = saved["permutation"].long()
        generator.set_state(saved["data_generator_state"])
        best_validation_loss = float(saved.get("best_validation_loss", float("inf")))
        torch.set_rng_state(saved["torch_rng_state"].cpu())
        if torch.cuda.is_available() and saved.get("cuda_rng_state_all"):
            torch.cuda.set_rng_state_all(saved["cuda_rng_state_all"])
        if permutation.numel() != train_count:
            raise ValueError("Resume checkpoint belongs to a different training corpus length")
        if not 0 <= batch_cursor <= train_count:
            raise ValueError("Resume checkpoint has an invalid data cursor")

    model.train()
    while start_epoch < training_config.epochs and global_step < training_config.max_steps:
        if batch_cursor >= train_count:
            start_epoch += 1
            batch_cursor = 0
            if start_epoch >= training_config.epochs:
                break
            permutation = torch.randperm(train_count, generator=generator)
            continue

        optimizer.zero_grad(set_to_none=True)
        micro_batches = []
        cursor = batch_cursor
        for _ in range(training_config.gradient_accumulation_steps):
            if cursor >= train_count:
                break
            chosen = permutation[cursor:min(cursor + training_config.batch_size, train_count)].tolist()
            batch = torch.stack([
                torch.tensor(train_tokens[i:i + block_size + 1], dtype=torch.long) for i in chosen
            ])
            micro_batches.append(batch)
            cursor += len(chosen)
        if not micro_batches:
            break

        step_loss = 0.0
        for batch in micro_batches:
            inputs, targets = batch[:, :-1].to(device), batch[:, 1:].to(device)
            logits = model(inputs)
            loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), targets.reshape(-1))
            if not torch.isfinite(loss):
                raise FloatingPointError("Non-finite training loss")
            (loss / len(micro_batches)).backward()
            step_loss += float(loss.detach().cpu()) / len(micro_batches)

        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        scheduler.step()
        global_step += 1
        batch_cursor = cursor
        history.append(step_loss)

        if global_step % training_config.checkpoint_every_steps == 0 or global_step >= training_config.max_steps:
            payload = _make_payload(
                model, optimizer, scheduler, training_config, model_config, tokenizer,
                global_step=global_step, epoch=start_epoch, batch_cursor=batch_cursor,
                permutation=permutation, generator=generator,
                best_validation_loss=best_validation_loss, source=source.strip(),
                license_note=license_note.strip(),
            )
            _atomic_save(payload, latest_path)

    validation_loss = _evaluate(model, validation_tokens, block_size, training_config.batch_size, device)
    if validation_loss < best_validation_loss:
        best_validation_loss = validation_loss
        final_payload = _make_payload(
            model, optimizer, scheduler, training_config, model_config, tokenizer,
            global_step=global_step, epoch=start_epoch, batch_cursor=batch_cursor,
            permutation=permutation, generator=generator,
            best_validation_loss=best_validation_loss, source=source.strip(),
            license_note=license_note.strip(),
        )
        _atomic_save(final_payload, target / "best-validation.pt")

    final_payload = _make_payload(
        model, optimizer, scheduler, training_config, model_config, tokenizer,
        global_step=global_step, epoch=start_epoch, batch_cursor=batch_cursor,
        permutation=permutation, generator=generator,
        best_validation_loss=best_validation_loss, source=source.strip(),
        license_note=license_note.strip(),
    )
    _atomic_save(final_payload, latest_path)
    _atomic_save(final_payload, target / "vayron-small.pt")
    report = {
        "checkpoint": str(target / "vayron-small.pt"),
        "resume_checkpoint": str(latest_path),
        "steps": global_step,
        "final_train_loss": history[-1] if history else None,
        "validation_loss": validation_loss,
        "best_validation_loss": best_validation_loss,
        "device": str(device),
        "gradient_accumulation_steps": training_config.gradient_accumulation_steps,
        "trained_from_random_initialization": resume_from is None,
        "resumed_from": str(resume_from) if resume_from is not None else None,
        "data_provenance": {"source": source.strip(), "license_note": license_note.strip()},
        "warning": "Baseline training only. Model quality depends on corpus scale, quality, diversity and evaluation.",
    }
    report_path = target / "training-report.json"
    temporary_report = report_path.with_name(report_path.name + ".tmp")
    temporary_report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    os.replace(temporary_report, report_path)
    return report


def load_checkpoint_bundle(path: str | Path, *, device: str = "cpu") -> tuple[VayronLanguageModel, dict]:
    """Load and validate a Vayron checkpoint and its tokenizer/provenance metadata."""
    checkpoint = torch.load(Path(path), map_location=device, weights_only=True)
    if not isinstance(checkpoint, dict) or checkpoint.get("format_version") != CHECKPOINT_FORMAT_VERSION:
        raise ValueError("Unsupported or invalid Vayron checkpoint format")
    provenance = checkpoint.get("data_provenance")
    if not isinstance(provenance, dict) or not str(provenance.get("source", "")).strip() or not str(provenance.get("license_note", "")).strip():
        raise ValueError("Checkpoint is missing training-data source or license provenance")
    tokenizer = VayronByteTokenizer()
    if checkpoint.get("tokenizer") != tokenizer.to_dict():
        raise ValueError("Checkpoint tokenizer does not match this Vayron runtime")
    config_data, state_dict = checkpoint.get("model_config"), checkpoint.get("model_state_dict")
    if not isinstance(config_data, dict) or not isinstance(state_dict, dict):
        raise ValueError("Checkpoint is missing model configuration or weights")
    try:
        config = VayronModelConfig(**config_data)
        if config.vocab_size != tokenizer.vocab_size:
            raise ValueError("Checkpoint vocabulary does not match tokenizer")
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
