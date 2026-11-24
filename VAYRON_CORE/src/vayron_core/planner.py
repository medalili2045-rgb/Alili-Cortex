"""Deterministic task planning primitives; no hidden model claims."""
from dataclasses import dataclass


@dataclass(frozen=True)
class TaskPlan:
    goal: str
    steps: tuple[str, ...]
    requires_external_evidence: bool = False
    requires_user_approval: bool = False


class TaskPlanner:
    def plan(self, goal: str) -> TaskPlan:
        clean = goal.strip()
        if not clean:
            raise ValueError("Goal cannot be empty")
        lower = clean.casefold()
        if any(word in lower for word in ("deploy", "publish", "نشر", "انشر", "حذف", "delete", "payment", "دفع")):
            return TaskPlan(clean, ("Clarify scope and target", "Inspect permissions and risks", "Prepare a reversible plan", "Request explicit approval before external changes"), requires_user_approval=True)
        if any(word in lower for word in ("research", "search", "بحث", "ابحث")):
            return TaskPlan(clean, ("Define the research question", "Collect traceable sources", "Compare evidence and limitations", "Summarize findings with citations"), requires_external_evidence=True)
        if any(word in lower for word in ("code", "build", "app", "برمج", "أنشئ", "تطبيق")):
            return TaskPlan(clean, ("Clarify requirements", "Design a modular implementation", "Implement the smallest testable increment", "Run tests and inspect failures", "Document limitations"))
        return TaskPlan(clean, ("Understand the request", "Break it into verifiable parts", "Work through each part", "Check the result and state uncertainties"))
