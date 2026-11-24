"""Vayron's first transparent multi-head orchestration layer."""
from dataclasses import dataclass
from .heads import HeadRouter, HeadSpec
from .planner import TaskPlanner, TaskPlan
from .verification import ResultVerifier, VerificationReport


@dataclass(frozen=True)
class NetworkTrace:
    selected_head: str
    plan: TaskPlan
    verification: VerificationReport
    mode: str = "foundation_orchestration"


class VayronNetwork:
    def __init__(
        self,
        router: HeadRouter | None = None,
        planner: TaskPlanner | None = None,
        verifier: ResultVerifier | None = None,
    ) -> None:
        self.router = router or HeadRouter()
        self.planner = planner or TaskPlanner()
        self.verifier = verifier or ResultVerifier()

    def inspect(self, request: str) -> NetworkTrace:
        if not request.strip():
            raise ValueError("Request cannot be empty")
        head: HeadSpec = self.router.route(request)
        plan = self.planner.plan(request)
        report = self.verifier.verify_plan(plan.goal, plan.steps)
        return NetworkTrace(head.name, plan, report)

    def status(self) -> dict:
        return {
            "network": "VAYRON_NETWORK",
            "mode": "foundation_orchestration",
            "trained_model_loaded": False,
            "external_api_required": False,
            "head_count": len(self.router.all_heads()),
            "heads": [head.name for head in self.router.all_heads()],
            "autonomous_weight_training": False,
        }
