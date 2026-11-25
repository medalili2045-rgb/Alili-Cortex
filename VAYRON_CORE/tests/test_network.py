import pytest

from vayron_core.heads import HeadRouter
from vayron_core.learning import LearningCandidate, LearningJournal
from vayron_core.network import VayronNetwork


def test_heads_are_unique_and_follow_naming_contract():
    heads = HeadRouter().all_heads()
    names = [head.name for head in heads]
    assert len(names) == len(set(names))
    assert all(name.endswith("_yzn") for name in names)
    assert len(heads) == 18


def test_router_selects_code_head():
    assert HeadRouter().route("Please write Python code").name == "CODE_yzn"


def test_network_produces_verifiable_plan():
    trace = VayronNetwork().inspect("Build a small application")
    assert trace.selected_head == "BUILD_yzn"
    assert trace.verification.passed
    assert trace.mode == "foundation_orchestration"


def test_network_rejects_empty_request():
    with pytest.raises(ValueError):
        VayronNetwork().inspect("  ")


class FakeMemory:
    def __init__(self):
        self.records = []

    def add(self, content, category="general"):
        self.records.append((content, category))
        return len(self.records)


def test_learning_requires_review_and_provenance():
    memory = FakeMemory()
    journal = LearningJournal(memory)
    candidate = LearningCandidate("A useful fact", "docs", "MIT", reviewed=False)
    with pytest.raises(PermissionError):
        journal.ingest(candidate)
    accepted = LearningCandidate("A useful fact", "docs", "MIT", reviewed=True)
    assert journal.ingest(accepted) == 1
    assert memory.records[0][1] == "reviewed_knowledge"
