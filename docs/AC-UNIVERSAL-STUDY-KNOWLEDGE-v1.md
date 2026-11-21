# AC Universal Study & Knowledge Engine v1

## Purpose

Provide a local-first, auditable path from curated ecosystem references to reviewable knowledge artifacts. This first implementation is deliberately a safe foundation, not an autonomous web crawler or a claim that AC has mastered external projects.

## Implemented in v1

- Accepts caller-supplied text excerpts for a known `source_id` in the AC ecosystem catalog.
- Enforces content-size, title, version, URL and license-status validation.
- Stores each evidence snapshot in SQLite with SHA-256, source identity, version, URL, timestamp and license-review metadata.
- Places every new evidence record in `quarantined`, even if the caller reports a license status of `approved`.
- Creates deterministic study reports using lexical overlap to select candidate passages.
- Compares evidence sets using shared and distinctive terms while explicitly avoiding claims of semantic agreement.
- Runs structural provenance checks and reports semantic accuracy as `not_evaluated`.
- Can propose a report to the existing KnowledgeStore only after structural checks pass. The artifact remains `proposed`; it is not validated, approved or published automatically.

## Authenticated API

All endpoints below require the existing Bearer token.

### Add local evidence

`POST /v1/study/evidence`

Example request:

```json
{
  "source_id": "hf_transformers",
  "title": "Model architecture notes",
  "content": "Caller-supplied, permitted documentation excerpt...",
  "artifact_url": "https://huggingface.co/docs/transformers",
  "version": "pinned-release-or-commit",
  "license_status": "review_required"
}
```

The response includes the evidence ID, SHA-256 and `status=quarantined`. No URL is fetched by this endpoint.

### List and inspect evidence

- `GET /v1/study/evidence?limit=50` returns metadata without content.
- `GET /v1/study/evidence/{evidence_id}` returns the stored evidence record.

### Create a study session

`POST /v1/study/sessions`

```json
{
  "question": "Compare model architecture and tokenizer responsibilities",
  "domain": "language",
  "evidence_ids": ["evidence-uuid-1", "evidence-uuid-2"]
}
```

The report preserves evidence IDs, source IDs, hashes, license metadata, selected passages and limitations.

### Evaluate and propose knowledge

- `POST /v1/study/sessions/{session_id}/evaluate` runs structural checks only.
- `POST /v1/study/sessions/{session_id}/propose-knowledge` creates a KnowledgeStore artifact in `proposed` state after structural checks pass.
- `GET /v1/study/sessions` and `GET /v1/study/sessions/{session_id}` retrieve study records.

Knowledge publication still follows the existing proposed → quarantined → validated → approved → published governance flow and requires explicit human review.

## Safety boundaries

- No network crawler, repository clone, package installation or third-party runtime is introduced.
- No retrieved text or code is executed. Evidence is treated as untrusted input.
- No license is inferred from a public URL. A caller-supplied `approved` label is metadata, not legal clearance; all evidence remains quarantined and proposed knowledge uses `review_required`.
- Structural checks are not semantic fact-checking, scientific validation, benchmark results or legal advice.
- No automatic routing into brain memory, no model-weight updates, no production code changes and no paid services.
- The 64,000-character evidence limit and 12-item session limit bound local resource use.

## Next implementation stages

1. Add a controlled source connector for official public documentation with domain allowlists, rate limits, version pinning, checksums and content-type validation.
2. Add parsers for Markdown, HTML, PDF and repository metadata without executing retrieved content.
3. Add semantic extraction through a configured local model, preserving exact evidence spans and model/version provenance.
4. Add reproducible sandbox adapters for selected experiments, disabled by default and isolated from secrets and production.
5. Add independent-source verification, conflict detection and benchmark-backed evaluation.
6. Add an explicit approval interface for publishing selected knowledge to specialist brains.

Each stage must remain independently testable and must not silently promote evidence or alter model weights.
