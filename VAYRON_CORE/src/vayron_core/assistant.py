"""Local-first assistant composition across routing, planning, and model runtime."""
from dataclasses import dataclass
from .model_runtime import ModelRuntime
from .network import VayronNetwork


@dataclass(frozen=True)
class AssistantReply:
    answer: str
    selected_head: str
    plan_steps: tuple[str, ...]
    verification_passed: bool


class VayronAssistant:
    def __init__(
        self,
        model_runtime: ModelRuntime,
        *,
        model_name: str,
        network: VayronNetwork | None = None,
    ) -> None:
        if not model_name.strip():
            raise ValueError("model_name cannot be empty")
        self.model_runtime = model_runtime
        self.model_name = model_name
        self.network = network or VayronNetwork()

    def chat(self, message: str, *, max_new_tokens: int = 512) -> AssistantReply:
        trace = self.network.inspect(message)
        answer = self.model_runtime.generate(
            self.model_name,
            message,
            max_new_tokens=max_new_tokens,
        )
        return AssistantReply(
            answer=answer,
            selected_head=trace.selected_head,
            plan_steps=trace.plan.steps,
            verification_passed=trace.verification.passed,
        )
