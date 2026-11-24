import pytest
torch = pytest.importorskip("torch")

from vayron_core.neural import VayronModelConfig
from vayron_core.training import TrainingConfig, train_text
from vayron_core.torch_adapter import TorchCheckpointAdapter


def test_checkpoint_adapter_runs_local_generation(tmp_path):
    report = train_text(
        "A tiny original Vayron training corpus. " * 100,
        tmp_path,
        source="test-data",
        license_note="CC0 test data",
        model_config=VayronModelConfig(d_model=32, n_heads=4, n_layers=1, max_seq_len=16, dropout=0.0),
        training_config=TrainingConfig(batch_size=2, max_steps=1, device="cpu"),
    )
    adapter = TorchCheckpointAdapter(report["checkpoint"])
    assert adapter.descriptor.name == "vayron-local"
    result = adapter.generate("Vayron", max_new_tokens=2)
    assert isinstance(result, str)


def test_checkpoint_adapter_rejects_missing_file(tmp_path):
    from vayron_core.torch_adapter import TorchCheckpointAdapter
    with pytest.raises(FileNotFoundError):
        TorchCheckpointAdapter(tmp_path / "missing.pt")
