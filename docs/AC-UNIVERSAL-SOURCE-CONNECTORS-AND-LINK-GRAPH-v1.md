# AC Universal Source Connectors & Link Graph v1

## Purpose
Add bounded, free-first retrieval of public documentation from sources already present in the AC ecosystem catalog, then preserve explicit provenance relationships across source, evidence, study session, proposed knowledge and specialist-brain records.

## Source connector boundary
- The connector accepts only a catalogued `source_id` and an HTTPS artifact URL on that source's exact canonical hostname.
- DNS answers are checked for globally routable addresses and the chosen address is pinned for the TLS connection; certificate verification and hostname SNI remain enabled.
- Redirects are limited to three hops and every destination is revalidated against the same catalog host and public-address rules.
- Requests have an eight-second timeout, no proxy inheritance, a 1 MB response ceiling, and a strict text/HTML/Markdown/JSON content-type allowlist.
- HTML script, style, SVG and noscript contents are discarded. PDF, archives, binary data and executable content are not accepted in v1.
- ETag and Last-Modified are recorded as version hints; callers may send them back as If-None-Match / If-Modified-Since validators to receive a 304 not-modified result without duplicating evidence. They are not cryptographic version identities. A SHA-256 digest is computed over normalized text.
- The connector has no retry loop, crawler, recursive link traversal, package installation, shell, or code execution.
- Retrieved text is stored as quarantined study evidence with license review required. License headers are advisory metadata, never legal clearance.

## Linking model
Typed, idempotent graph edges connect:
- source `documents` evidence
- evidence `studied_in` session
- session `proposes` knowledge
- evidence `supports` knowledge
- knowledge `assigned_to` specialist brain
- evidence `compares_with` / `corroborates` evidence
- source/source and knowledge/knowledge `related_to`

Links store endpoint types and IDs, relation, optional bounded metadata, and timestamp. Evidence-to-session, session-to-knowledge, evidence-to-knowledge and knowledge-to-origin-brain edges are created as the study workflow progresses; source-to-evidence edges are created on intake. Node payloads, brain responsibilities and model weights remain separate. Manual relationship creation validates that both endpoints exist. No relationship automatically approves or publishes knowledge.

## API
- `POST /v1/connectors/fetch` (authenticated): `{ "source_id": "...", "artifact_url": "https://same-catalog-host/...", "if_none_match": "...", "if_modified_since": "..." }`. Fetches one document and creates quarantined evidence; a 304 returns `not_modified` and creates no duplicate record.
- `POST /v1/links` (authenticated): creates one typed link after validating both nodes.
- `GET /v1/links?node_type=evidence&node_id=...` (authenticated): lists links touching a node; omit both query fields to list recent links.

## Limitations
This is deterministic document intake and explicit graph storage, not semantic extraction, automatic concept discovery, web-wide crawling, independent license verification, or autonomous brain learning. Only text-like documents from exact catalogued hosts are supported. No paid APIs or paid fallback are used.
