"""AC Knowledge Scout Navigator v1.

Uses the existing catalog-bound, DNS-pinned UniversalSourceConnector.
Extracts short structural learning notes only; no LLM claims, bulk mirroring,
package execution, or automatic publication.
"""
from __future__ import annotations

import re


class KnowledgeScoutNavigator:
    MAX_NOTE_CHARS = 2_400
    MAX_ITEMS = 12

    def __init__(self, scout, connector):
        self.scout = scout
        self.connector = connector

    @staticmethod
    def _extract_structured_note(content: str) -> str:
        if not isinstance(content, str) or not content.strip():
            raise ValueError("source_content_empty")
        lines = [line.strip() for line in content.splitlines()]
        selected = []
        in_code = False
        for line in lines:
            if line.startswith("```") or line.startswith("~~~"):
                in_code = not in_code
                continue
            if in_code or not line:
                continue
            if re.match(r"^(#{1,4}\s+|[-*+]\s+|\d{1,3}[.)]\s+)", line):
                clean = re.sub(r"^#{1,4}\s+|^[-*+]\s+|^\d{1,3}[.)]\s+", "", line).strip()
                if len(clean) >= 18:
                    selected.append(clean[:320])
        if not selected:
            for paragraph in re.split(r"\n\s*\n", content):
                candidate = re.sub(r"\s+", " ", paragraph).strip()
                if len(candidate) < 45:
                    continue
                for sentence in re.split(r"(?<=[.!?])\s+", candidate):
                    sentence = sentence.strip()
                    if 45 <= len(sentence) <= 280:
                        selected.append(sentence)
                        break
                if len(selected) >= 5:
                    break
        unique = []
        seen = set()
        for item in selected:
            key = item.casefold()
            if key not in seen:
                seen.add(key)
                unique.append(item)
            if len(unique) >= KnowledgeScoutNavigator.MAX_ITEMS:
                break
        if not unique:
            raise ValueError("no_structured_learning_candidates_found")
        note = "Extracted learning points (structural extraction; verify against source):\n"
        note += "\n".join(f"- {item}" for item in unique)
        return note[:KnowledgeScoutNavigator.MAX_NOTE_CHARS]

    def discover(self, *, source_id: str, artifact_url: str | None = None,
                 domain: str, brain_id: str) -> dict:
        source = self.scout.get_source(source_id)
        if source is None:
            raise KeyError("scout_source_not_found")
        if not source["enabled"]:
            raise ValueError("scout_source_not_enabled")
        fetched = self.connector.fetch(source_id, artifact_url)
        if fetched.get("not_modified"):
            return {"status": "not_modified", "source_id": source_id,
                    "artifact_url": fetched["artifact_url"],
                    "retrieved_at": fetched["retrieved_at"]}
        note = self._extract_structured_note(fetched["content"])
        proposal = self.scout.propose(
            source_id=source_id, title=fetched["title"][:300], note=note,
            domain=domain, brain_id=brain_id,
            source_url=fetched["artifact_url"],
            retrieved_at=fetched["retrieved_at"],
        )
        return {"status": "quarantined", "proposal": proposal,
                "fetch": {key: fetched.get(key) for key in
                          ("artifact_url", "retrieved_at", "content_type",
                           "sha256", "etag", "last_modified", "redirect_count")},
                "extraction_method": "structural_rules_v1",
                "notice": "short_note_quarantined_not_published"}
