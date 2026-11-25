"""Training utilities for image-caption alignment in Vayron.

The pretrained SigLIP encoder stays frozen. Only its Vayron projector and the
small Vayron language model are optimized. This module deliberately accepts
already-loaded image/caption batches; dataset download and license review remain
the caller's responsibility.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Sequence

import torch
import torch.nn.functional as F

from .tokenizer import VayronByteTokenizer


def multimodal_caption_step(
    images: Sequence[object],
    captions: Sequence[str],
    *,
    vision,
    language_model,
    optimizer: torch.optim.Optimizer,
    tokenizer: VayronByteTokenizer | None = None,
    max_caption_tokens: int | None = None,
    grad_clip_norm: float = 1.0,
) -> dict[str, float]:
    """Perform one teacher-forced image-caption training step.

    Captions are UTF-8 byte-tokenized with BOS/EOS. Padding is excluded from
    loss. The visual encoder must be frozen; its projector remains trainable.
    """
    if not images or len(images) != len(captions):
        raise ValueError("images and captions must be non-empty and have equal lengths")
    if any(not isinstance(c, str) or not c.strip() for c in captions):
        raise ValueError("every caption must be a non-empty string")
    if grad_clip_norm <= 0:
        raise ValueError("grad_clip_norm must be positive")

    tokenizer = tokenizer or VayronByteTokenizer()
    device = next(language_model.parameters()).device
    encoded = [tokenizer.encode(c.strip(), add_bos=True, add_eos=True) for c in captions]
    target_length = max(len(row) for row in encoded)
    if max_caption_tokens is not None:
        if max_caption_tokens < 2:
            raise ValueError("max_caption_tokens must be >= 2")
        target_length = min(target_length, max_caption_tokens)
    encoded = [row[:target_length] for row in encoded]
    # Preserve EOS when truncating long captions.
    for row in encoded:
        if row[-1] != tokenizer.config.eos_id:
            row[-1] = tokenizer.config.eos_id

    tokens = torch.full(
        (len(encoded), target_length), tokenizer.config.pad_id,
        dtype=torch.long, device=device,
    )
    for index, row in enumerate(encoded):
        tokens[index, :len(row)] = torch.tensor(row, dtype=torch.long, device=device)
    input_ids, targets = tokens[:, :-1], tokens[:, 1:]
    valid_targets = targets.ne(tokenizer.config.pad_id)

    visual_tokens = vision(images)
    if visual_tokens.device != device:
        raise ValueError("vision projector output and language model must share a device")
    if visual_tokens.shape[0] != len(captions):
        raise ValueError("vision output batch size does not match captions")
    if visual_tokens.shape[1] + input_ids.shape[1] > language_model.config.max_seq_len:
        raise ValueError("visual tokens plus caption tokens exceed model context length")

    language_model.train()
    vision.train()
    optimizer.zero_grad(set_to_none=True)
    logits = language_model.forward_multimodal(input_ids, visual_tokens)
    loss = F.cross_entropy(
        logits.reshape(-1, logits.shape[-1]),
        targets.reshape(-1),
        ignore_index=tokenizer.config.pad_id,
    )
    if not torch.isfinite(loss):
        raise FloatingPointError("non-finite multimodal caption loss")
    loss.backward()

    projector_parameters = [
        p for p in vision.projector.parameters() if p.requires_grad
    ]
    language_parameters = [
        p for p in language_model.parameters() if p.requires_grad
    ]
    if not any(p.grad is not None for p in projector_parameters):
        raise RuntimeError("visual projector received no gradients")
    if not any(p.grad is not None for p in language_parameters):
        raise RuntimeError("language model received no gradients")
    if any(p.requires_grad for p in vision.encoder.parameters()):
        raise RuntimeError("SigLIP encoder must remain frozen")

    torch.nn.utils.clip_grad_norm_(
        projector_parameters + language_parameters, grad_clip_norm
    )
    optimizer.step()
    token_count = int(valid_targets.sum().item())
    return {"loss": float(loss.detach().cpu()), "target_tokens": token_count}


def save_multimodal_checkpoint(
    path: str | Path,
    *,
    vision,
    language_model,
    optimizer: torch.optim.Optimizer,
    step: int,
    source: str,
    license_note: str,
) -> None:
    """Atomically save trainable weights and optimizer, excluding frozen SigLIP."""
    if step < 0 or not source.strip() or not license_note.strip():
        raise ValueError("step, source, and license_note must be valid")
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    payload = {
        "format_version": 1,
        "step": int(step),
        "vision_projector": vision.projector.state_dict(),
        "language_model": language_model.state_dict(),
        "optimizer": optimizer.state_dict(),
        "source": source.strip(),
        "license_note": license_note.strip(),
        "frozen_vision_model": getattr(vision, "MODEL_ID", "external frozen encoder"),
    }
    try:
        torch.save(payload, temporary)
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
