import pytest
import torch

from vayron_core.neural import VayronLanguageModel, VayronModelConfig
from vayron_core.vision import VayronVisionProjector


def test_vision_projector_bounds_tokens_and_backpropagates():
    projector = VayronVisionProjector(input_dim=32, output_dim=128, max_visual_tokens=16)
    features = torch.randn(2, 196, 32)
    output = projector(features)
    assert output.shape == (2, 16, 128)
    output.mean().backward()
    assert projector.projection[0].weight.grad is not None


def test_multimodal_forward_returns_text_logits():
    config = VayronModelConfig(d_model=128, n_heads=4, n_layers=2, max_seq_len=32)
    model = VayronLanguageModel(config)
    input_ids = torch.randint(0, config.vocab_size, (2, 8))
    image_embeddings = torch.randn(2, 16, config.d_model)
    logits = model.forward_multimodal(input_ids, image_embeddings)
    assert logits.shape == (2, 8, config.vocab_size)


def test_multimodal_forward_rejects_context_overflow():
    config = VayronModelConfig(d_model=128, n_heads=4, n_layers=1, max_seq_len=16)
    model = VayronLanguageModel(config)
    input_ids = torch.randint(0, config.vocab_size, (1, 2))
    image_embeddings = torch.randn(1, 15, config.d_model)
    with pytest.raises(ValueError, match="max_seq_len"):
        model.forward_multimodal(input_ids, image_embeddings)
