"""Review-gated knowledge intake. This records knowledge; it does not train weights."""
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Protocol


class MemoryBackend(Protocol):
    def add(self, content: str, category: str = "general") -> object: ...


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
        record = {
            **asdict(candidate),
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "kind": "knowledge_record_not_weight_training",
        }
        return self.memory.add(json.dumps(record, ensure_ascii=False), category="reviewed_knowledge")
