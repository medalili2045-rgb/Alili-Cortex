from vayron_core.assistant import VayronAssistant
from vayron_core.model_runtime import ModelDescriptor, ModelRuntime


class FakeLocalModel:
    descriptor = ModelDescriptor("vayron-test", "0.0.1", "test-double", "none", "test fixture")

    def generate(self, prompt, *, max_new_tokens=512):
        return "Vayron answer: " + prompt


def test_assistant_routes_plans_and_generates_locally():
    runtime = ModelRuntime()
    runtime.register(FakeLocalModel())
    assistant = VayronAssistant(runtime, model_name="vayron-test")
    reply = assistant.chat("Build a Python application")
    assert reply.answer == "Vayron answer: Build a Python application"
    assert reply.selected_head == "BUILD_yzn"
    assert reply.verification_passed is True
    assert len(reply.plan_steps) > 0


def test_assistant_requires_model_name():
    runtime = ModelRuntime()
    try:
        VayronAssistant(runtime, model_name=" ")
    except ValueError:
        pass
    else:
        raise AssertionError("empty model name must fail")
