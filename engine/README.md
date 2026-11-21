# AC Open Ecosystem Intelligence v1

This slice adds a curated discovery catalog for open libraries, research indexes and developer tools across AI and non-AI domains.

## What is included

- A seed catalog of 53 public discovery targets from Hugging Face, Meta, Google, OpenAI, DeepSeek, Qwen, PyTorch and independent open-source communities.
- Domain filters covering language, code, math, science, medicine, biology, chemistry, engineering, CAD, 3D, vision, audio, video, robotics, agents, retrieval, evaluation, geography, history and more.
- Searchable metadata and per-source study focus.
- A strict study policy covering source identity, version/commit, artifact hashes, provenance, license review, deduplication, cross-source verification, sandbox experiments and controlled publication.
- Authenticated read-only API endpoints:
  - `GET /v1/ecosystem`
  - `GET /v1/ecosystem?domain=robotics`
  - `GET /v1/ecosystem?q=vector&limit=10`
  - `GET /v1/ecosystem/{source_id}`
  - `GET /v1/ecosystem/policy`

## Important capability boundary

This is a **catalog and learning-policy foundation**, not a crawler or completed ingestion pipeline. No external repository, model, dataset, paper or documentation has been downloaded or ingested by this change. The API only returns catalog metadata.

A public repository URL does not mean every model checkpoint, dataset, documentation page, dependency or training artifact is licensed for unrestricted use. AC must review the exact artifact and version. Unknown or incompatible licenses are quarantined. No paid API, subscription, automatic install, external code execution or automatic weight update is permitted.

## Recommended study pipeline

1. Discover official project and documentation endpoints.
2. Resolve exact version, owner, commit and artifact.
3. Review licenses separately for source code, model weights, datasets, documentation and dependencies.
4. Collect only permitted material and preserve source references.
5. Parse APIs, algorithms, examples, constraints and citations.
6. Normalize, hash and deduplicate.
7. Build domain concept maps and dependency graphs.
8. Cross-check against independent sources and reproducible tests.
9. Experiment only in an isolated, resource-limited sandbox.
10. Publish validated knowledge for shared retrieval by AC brains; production changes and weight updates remain approval-gated.

## Current status

- Catalog: seeded and searchable.
- External ingestion: not implemented.
- Automatic learning: not enabled.
- Sandbox execution: not implemented by this slice.
- Model training: not performed.
- Paid services: prohibited.


## AC Learning Blueprints v1

Structured study plans map catalog sources to specialist brains, with lesson objectives, study actions and evaluation deliverables. Query the authenticated `GET /v1/learning/blueprints` endpoint, optionally filtering by `brain_id` or `domain`. These are study plans only: no source ingestion, automatic learning or model-weight update is claimed. See [AC Learning Blueprints v1](../docs/AC-LEARNING-BLUEPRINTS-v1.md).

## AC Autonomous Learning Worker v1

The separate-process worker runs bounded source-study cycles immediately and then on a configurable interval (24 hours by default). It is independent of the API process, but requires a powered-on host with persistent storage and outbound HTTPS. See [AC Autonomous Learning Worker v1](../docs/AC-AUTONOMOUS-LEARNING-WORKER-v1.md).

Install the engine from this directory and run `python -m alili_engine.autonomous_worker --once` for one cycle. Use `--status`, `--pause`, and `--resume` to inspect and control the scheduler.

Fetched evidence remains quarantined with `review_required` license status. The worker does not self-approve licenses, publish knowledge, train model weights, install packages, or execute retrieved code.

## AC Universal Library Foundry v1

The engine now includes a persistent, quarantine-first library registry with version and provenance metadata, artifact SHA-256 fingerprinting, duplicate detection, domain and specialist-brain mapping, and artifact-scoped license review. Authenticated API:
- GET /v1/libraries
- GET /v1/libraries/{library_id}
- POST /v1/libraries
- POST /v1/libraries/{library_id}/review

The registry does not download, install, import, or execute third-party code. New entries remain quarantined unless a supported license and explicit HTTPS evidence are reviewed. This is governance and metadata infrastructure, not a downloaded or installed library corpus. See ../docs/AC-UNIVERSAL-LIBRARY-FOUNDRY-v1.md.
