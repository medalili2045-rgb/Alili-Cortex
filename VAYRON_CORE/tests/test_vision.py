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



def test_projector_to_language_model_integration_backpropagates():
    """Verify projected visual tokens reach the decoder and train both sides."""
    config = VayronModelConfig(
        d_model=128, n_heads=4, n_layers=2, max_seq_len=32, dropout=0.0
    )
    projector = VayronVisionProjector(
        input_dim=32, output_dim=config.d_model, max_visual_tokens=16
    )
    model = VayronLanguageModel(config)

    patch_features = torch.randn(2, 196, 32, requires_grad=True)
    input_ids = torch.randint(0, config.vocab_size, (2, 8))

    visual_tokens = projector(patch_features)
    logits = model.forward_multimodal(input_ids, visual_tokens)

    assert visual_tokens.shape == (2, 16, config.d_model)
    assert logits.shape == (2, 8, config.vocab_size)
    assert torch.isfinite(logits).all()

    loss = logits.float().square().mean()
    loss.backward()

    assert projector.projection[0].weight.grad is not None
    assert torch.isfinite(projector.projection[0].weight.grad).all()
    assert model.token_embedding.weight.grad is not None
    assert torch.isfinite(model.token_embedding.weight.grad).all()
    assert patch_features.grad is not None
    assert torch.isfinite(patch_features.grad).all()


def test_multimodal_forward_rejects_mismatched_devices():
    if not torch.cuda.is_available():
        pytest.skip("CUDA is required to check cross-device inputs")
    config = VayronModelConfig(d_model=32, n_heads=4, n_layers=1, max_seq_len=16)
    model = VayronLanguageModel(config)
    input_ids = torch.randint(0, config.vocab_size, (1, 2), device="cpu")
    image_embeddings = torch.randn(1, 2, config.d_model, device="cuda")
    with pytest.raises(ValueError, match="same device"):
        model.forward_multimodal(input_ids, image_embeddings)
