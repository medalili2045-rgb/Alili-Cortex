"""Review-gated knowledge intake. This records knowledge; it does not train weights."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol


class MemoryBackend(Protocol):
    def add(self, content: str, metadata: dict | None = None) -> object: ...


@dataclass(frozen=True)
class LearningCandidate:
    content: str
    source: str
    license_note: str
    reviewed: bool = False


class LearningJournal:
    def __init__(self, memory: MemoryBackend) -> None:
        self.memory = memory

    def ingest(self, candidate: LearningCandidate) -> object:
        if not candidate.content.strip() or not candidate.source.strip():
            raise ValueError("Content and source are required")
        if not candidate.license_note.strip():
            raise ValueError("A license/provenance note is required")
        if not candidate.reviewed:
            raise PermissionError("Candidate must be reviewed before entering trusted memory")
        metadata = {
            "source": candidate.source,
            "license_note": candidate.license_note,
            "reviewed": True,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "kind": "knowledge_record_not_weight_training",
        }
        return self.memory.add(candidate.content, metadata)
