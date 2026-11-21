# AC Knowledge Scout v1

AC Knowledge Scout is a quarantine-first discovery control plane. This first
version supplies a persistent source registry, job queue/checkpoints, and
provenance-rich knowledge proposals.

## Current implementation boundary

- Source registration is limited to public HTTPS locations.
- Every source starts disabled. Enabling requires an explicit terms-review flag
  and a public HTTPS evidence URL.
- Jobs can be queued and checkpointed for later resumption.
- Proposals contain short notes/summaries (maximum 12,000 characters), a SHA-256
  fingerprint, source URL, retrieval timestamp, domain, brain assignment, and
  optional license-evidence URL.
- Proposals always enter quarantine. There is no approval, publication,
  package installation, code execution, network fetch, model inference, or
  automatic scraping in v1.
- Duplicate note fingerprints are rejected by the database uniqueness rule.

## API

All routes require the engine bearer token.

- `GET /v1/knowledge-scout/status`
- `GET /v1/knowledge-scout/sources`
- `GET /v1/knowledge-scout/jobs`
- `GET /v1/knowledge-scout/proposals`
- `POST /v1/knowledge-scout/sources`
- `POST /v1/knowledge-scout/jobs`
- `POST /v1/knowledge-scout/proposals`

## Security boundary before a future crawler

The URL validator rejects non-HTTPS URLs, credentials, nonstandard ports,
localhost, private IP literals, and local/internal hostnames. It is not by
itself sufficient for network fetching. A future fetcher must resolve DNS,
reject every non-global result, pin the validated destination, revalidate each
redirect, enforce response-size/time/content-type limits, apply per-host
rate limits, and respect robots, terms, authentication walls, and paywalls.
Do not fetch private/internal network targets or bulk-copy copyrighted works.

## Scheduling and availability

The queue/checkpoint model supports short, repeatable batches. It does not run
by itself, does not guarantee 24/7 uptime, and does not imply continuous model
training. A future free-tier scheduler must be separately checked against
provider terms, quotas, region support, and the no-card/no-billing policy.

Knowledge ingestion is retrieval/curation (RAG-ready material), not model-weight
training. All third-party material remains quarantined pending review through
AC License Intelligence and AC Universal Library Foundry.
