# AC Evolution Engine v1

## Purpose
AC Evolution Engine turns evidence-backed knowledge gaps into reviewable proposals
for native AC knowledge libraries and specialist brains. Growth is demand-driven,
not based on a fixed number of libraries or brains.

## Lifecycle
1. Knowledge Scout and evaluators identify a gap.
2. A proposal is created with a stable item ID, domain, rationale, and HTTPS evidence.
3. The proposal remains `pending_review`.
4. A reviewer approves or rejects it.
5. Approval records the decision only; a separate implementation, compatibility,
   license, resource, and security review is required before creation or activation.

## Safety boundaries
- No automatic brain creation or activation.
- No package download, installation, import, or execution.
- No automatic publication or model-weight training.
- HTTPS evidence references are provenance pointers, not proof of truth or license rights.
- Duplicate item IDs are rejected.
- Domain and input sizes are bounded.
- Human review is mandatory.

## Storage and API
SQLite table: `ac_evolution_proposals`.

Authenticated endpoints:
- `GET /v1/evolution/status`
- `GET /v1/evolution/proposals?status=pending_review&limit=50`
- `POST /v1/evolution/proposals`
- `POST /v1/evolution/proposals/{proposal_id}/review`

This version manages proposals only. It does not perform autonomous 24/7 research
or claim that proposed libraries/brains are operational.
