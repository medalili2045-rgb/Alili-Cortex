import torch
from torch import nn

from vayron_core.multimodal_training import multimodal_caption_step
from vayron_core.neural import VayronLanguageModel, VayronModelConfig


class FakeVision(nn.Module):
    def __init__(self, width=16, visual_tokens=4):
        super().__init__()
        self.encoder = nn.Linear(2, 2)
        for parameter in self.encoder.parameters():
            parameter.requires_grad_(False)
        self.projector = nn.Sequential(nn.Linear(width, width), nn.LayerNorm(width))
        self.features = torch.randn(1, visual_tokens, width)

    def forward(self, images):
        batch = len(images)
        features = self.features.expand(batch, -1, -1)
        return self.projector(features)


def test_multimodal_caption_step_updates_trainable_parts_and_freezes_encoder():
    torch.manual_seed(7)
    config = VayronModelConfig(
        vocab_size=259, d_model=16, n_heads=4, n_layers=1,
        max_seq_len=32, dropout=0.0,
    )
    vision = FakeVision(width=16, visual_tokens=4)
    language = VayronLanguageModel(config)
    optimizer = torch.optim.AdamW(
        list(vision.projector.parameters()) + list(language.parameters()),
        lr=1e-3,
    )
    before_projector = vision.projector[0].weight.detach().clone()
    before_language = language.token_embedding.weight.detach().clone()
    before_encoder = vision.encoder.weight.detach().clone()

    result = multimodal_caption_step(
        [object(), object()],
        ["a dog", "a red car"],
        vision=vision,
        language_model=language,
        optimizer=optimizer,
        max_caption_tokens=12,
    )

    assert result["target_tokens"] > 0
    assert torch.isfinite(torch.tensor(result["loss"]))
    assert not torch.equal(before_projector, vision.projector[0].weight)
    assert not torch.equal(before_language, language.token_embedding.weight)
    assert torch.equal(before_encoder, vision.encoder.weight)
    assert all(not parameter.requires_grad for parameter in vision.encoder.parameters())


def test_multimodal_caption_step_rejects_context_overflow():
    config = VayronModelConfig(
        vocab_size=259, d_model=16, n_heads=4, n_layers=1,
        max_seq_len=8, dropout=0.0,
    )
    vision = FakeVision(width=16, visual_tokens=4)
    language = VayronLanguageModel(config)
    optimizer = torch.optim.AdamW(
        list(vision.projector.parameters()) + list(language.parameters()),
        lr=1e-3,
    )

    try:
        multimodal_caption_step(
            [object()], ["this caption is much too long"],
            vision=vision, language_model=language, optimizer=optimizer,
        )
    except ValueError as exc:
        assert "context length" in str(exc)
    else:
        raise AssertionError("expected context overflow to be rejected")
