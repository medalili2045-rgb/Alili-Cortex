import pytest

from vayron_core.model_runtime import ModelDescriptor, ModelRuntime


class FakeLocalModel:
    descriptor = ModelDescriptor(
        name="vayron-test",
        version="0.0.1",
        architecture="test-double",
        weights_path="not-a-real-checkpoint",
        license_note="test fixture only",
    )

    def generate(self, prompt, *, max_new_tokens=512):
        return f"local:{prompt}:{max_new_tokens}"


def test_local_model_registration_and_generation():
    runtime = ModelRuntime()
    runtime.register(FakeLocalModel())
    assert runtime.generate("vayron-test", "hello") == "local:hello:512"
    assert runtime.status()["execution_mode"] == "local_only"


def test_runtime_rejects_duplicate_model():
    runtime = ModelRuntime()
    runtime.register(FakeLocalModel())
    with pytest.raises(ValueError):
        runtime.register(FakeLocalModel())


def test_runtime_rejects_unknown_model():
    with pytest.raises(LookupError):
        ModelRuntime().generate("missing", "hello")


def test_runtime_validates_generation_limits():
    runtime = ModelRuntime()
    runtime.register(FakeLocalModel())
    with pytest.raises(ValueError):
        runtime.generate("vayron-test", "hello", max_new_tokens=0)
