import pytest
torch = pytest.importorskip("torch")

from vayron_core.neural import VayronModelConfig
from vayron_core.training import TrainingConfig, train_text
from vayron_core.torch_adapter import TorchCheckpointAdapter


def _train_checkpoint(tmp_path):
    report = train_text(
        "A tiny original Vayron training corpus. " * 100,
        tmp_path,
        source="test-data",
        license_note="CC0 test data",
        model_config=VayronModelConfig(d_model=32, n_heads=4, n_layers=1, max_seq_len=16, dropout=0.0),
        training_config=TrainingConfig(batch_size=2, max_steps=1, device="cpu"),
    )
    return report["checkpoint"]


def test_checkpoint_adapter_runs_local_generation(tmp_path):
    adapter = TorchCheckpointAdapter(_train_checkpoint(tmp_path))
    assert adapter.descriptor.name == "vayron-local"
    result = adapter.generate("Vayron", max_new_tokens=2)
    assert isinstance(result, str)


def test_checkpoint_adapter_rejects_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        TorchCheckpointAdapter(tmp_path / "missing.pt")


def test_checkpoint_loader_rejects_tokenizer_mismatch(tmp_path):
    from vayron_core.training import load_checkpoint_bundle
    checkpoint = _train_checkpoint(tmp_path)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    payload["tokenizer"]["vocab_size"] = 300
    broken = tmp_path / "wrong-tokenizer.pt"
    torch.save(payload, broken)
    with pytest.raises(ValueError, match="tokenizer"):
        load_checkpoint_bundle(broken)


def test_checkpoint_loader_rejects_missing_provenance(tmp_path):
    from vayron_core.training import load_checkpoint_bundle
    checkpoint = _train_checkpoint(tmp_path)
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    payload["data_provenance"]["source"] = ""
    broken = tmp_path / "missing-source.pt"
    torch.save(payload, broken)
    with pytest.raises(ValueError, match="source or license"):
        load_checkpoint_bundle(broken)


def test_adapter_rejects_unbounded_generation_request(tmp_path):
    adapter = TorchCheckpointAdapter(_train_checkpoint(tmp_path))
    with pytest.raises(ValueError, match="between 1 and 2048"):
        adapter.generate("Vayron", max_new_tokens=2049)


def test_training_rejects_tokenizer_vocabulary_mismatch(tmp_path):
    with pytest.raises(ValueError, match="vocab_size"):
        train_text(
            "A tiny original Vayron training corpus. " * 100,
            tmp_path,
            source="test-data",
            license_note="CC0 test data",
            model_config=VayronModelConfig(vocab_size=300, d_model=32, n_heads=4, n_layers=1, max_seq_len=16, dropout=0.0),
            training_config=TrainingConfig(batch_size=2, max_steps=1, device="cpu"),
        )
