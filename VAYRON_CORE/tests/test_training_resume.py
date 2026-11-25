import pytest

torch = pytest.importorskip("torch")

from vayron_core.neural import VayronModelConfig
from vayron_core.training import TrainingConfig, load_checkpoint_bundle, train_text


def _configs(max_steps):
    model = VayronModelConfig(
        d_model=32, n_heads=4, n_layers=1, max_seq_len=16, dropout=0.0
    )
    training = TrainingConfig(
        epochs=1, batch_size=2, max_steps=max_steps, device="cpu",
        checkpoint_every_steps=1, gradient_accumulation_steps=2,
        warmup_steps=1,
    )
    return model, training


def test_checkpoint_contains_optimizer_scheduler_and_resume_cursor(tmp_path):
    corpus = "Vayron is an independently developed language model. " * 100
    model_config, training_config = _configs(2)
    first = train_text(
        corpus, tmp_path, source="unit-test-corpus",
        license_note="CC0 synthetic fixture",
        model_config=model_config, training_config=training_config,
    )
    saved = torch.load(first["resume_checkpoint"], map_location="cpu", weights_only=True)
    assert saved["global_step"] == 2
    assert "optimizer_state_dict" in saved
    assert "scheduler_state_dict" in saved
    assert "data_generator_state" in saved
    assert "permutation" in saved
    assert saved["format_version"] == 2


def test_resume_continues_optimizer_steps_and_loads_inference_checkpoint(tmp_path):
    corpus = "A resumable training loop must preserve its model and optimizer state. " * 100
    model_config, first_config = _configs(1)
    first = train_text(
        corpus, tmp_path, source="unit-test-corpus",
        license_note="CC0 synthetic fixture",
        model_config=model_config, training_config=first_config,
    )
    _, resumed_config = _configs(3)
    resumed = train_text(
        corpus, tmp_path, source="unit-test-corpus",
        license_note="CC0 synthetic fixture",
        model_config=model_config, training_config=resumed_config,
        resume_from=first["resume_checkpoint"],
    )
    assert resumed["steps"] == 3
    assert resumed["resumed_from"] == first["resume_checkpoint"]
    model, checkpoint = load_checkpoint_bundle(resumed["checkpoint"])
    assert model.training is False
    assert checkpoint["global_step"] == 3


def test_resume_rejects_changed_corpus_provenance(tmp_path):
    corpus = "Provenance must be checked before continuing training. " * 100
    model_config, training_config = _configs(1)
    first = train_text(
        corpus, tmp_path, source="original-source",
        license_note="CC0 synthetic fixture",
        model_config=model_config, training_config=training_config,
    )
    with pytest.raises(ValueError, match="provenance"):
        train_text(
            corpus, tmp_path, source="different-source",
            license_note="CC0 synthetic fixture",
            model_config=model_config, training_config=training_config,
            resume_from=first["resume_checkpoint"],
        )
