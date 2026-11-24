import pytest
torch = pytest.importorskip("torch")

from vayron_core.neural import VayronLanguageModel, VayronModelConfig
from vayron_core.training import TrainingConfig, load_checkpoint, train_text


def test_model_forward_shape_and_causal_mask():
    config = VayronModelConfig(d_model=32, n_heads=4, n_layers=2, max_seq_len=16)
    model = VayronLanguageModel(config)
    output = model(torch.randint(0, config.vocab_size, (2, 8)))
    assert output.shape == (2, 8, config.vocab_size)


def test_model_rejects_long_sequence():
    config = VayronModelConfig(d_model=32, n_heads=4, n_layers=1, max_seq_len=8)
    model = VayronLanguageModel(config)
    with pytest.raises(ValueError):
        model(torch.ones((1, 9), dtype=torch.long))


def test_tiny_training_creates_loadable_checkpoint_with_validation(tmp_path):
    report = train_text(
        ("Vayron learns from carefully licensed text. " * 100),
        tmp_path,
        source="test-fixture",
        license_note="CC0 test fixture",
        model_config=VayronModelConfig(d_model=32, n_heads=4, n_layers=1, max_seq_len=16, dropout=0.0),
        training_config=TrainingConfig(epochs=1, batch_size=2, max_steps=2, device="cpu"),
    )
    assert report["steps"] == 2
    assert report["trained_from_random_initialization"] is True
    assert report["validation_loss"] > 0
    model = load_checkpoint(report["checkpoint"])
    assert isinstance(model, VayronLanguageModel)


def test_training_requires_data_provenance(tmp_path):
    with pytest.raises(TypeError):
        train_text("A corpus " * 100, tmp_path)
