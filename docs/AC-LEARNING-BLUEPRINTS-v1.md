# AC Learning Blueprints v1

## Purpose

This slice turns the ecosystem catalog into structured, domain-specific study plans that AC can assign to its specialist brains. It does **not** claim that AC has already read the linked repositories, acquired datasets, learned their implementation details, or trained model weights.

## API

Authenticated read-only endpoint:

- `GET /v1/learning/blueprints`
- `GET /v1/learning/blueprints?brain_id=ac_code`
- `GET /v1/learning/blueprints?domain=audio`

Each blueprint identifies target brains, catalog source IDs, lessons, study actions and a concrete evaluation deliverable.

## Study-to-skill method

For each selected source and exact version:

1. Resolve the official repository, documentation, release and commit.
2. Review code, model, dataset, documentation and dependency licenses separately.
3. Record provenance, version, retrieval timestamp and content hashes.
4. Extract concepts, APIs, algorithms, design patterns, limits and known failure modes.
5. Convert findings into small lessons with examples and counterexamples.
6. Cross-check important claims against official documentation and independent references.
7. Create held-out tasks and reproducible tests.
8. Run experiments only in an isolated, resource-limited sandbox.
9. Propose a versioned skill artifact with citations and evaluation evidence.
10. Share approved artifacts with relevant brains through the existing knowledge lifecycle.

## Distribution

- Reasoning and math: `ac_reasoning`, `ac_science`
- Software and secure coding: `ac_code`, `ac_execution`
- Research and provenance: `ac_research`
- Retrieval and memory: `ac_memory`, `ac_research`
- Vision and documents: `ac_vision`
- Speech and media: `ac_media`, `ac_language`
- Strategy and controlled automation: `ac_strategy`, `ac_execution`

A lesson is reusable across brains only when its domain, prerequisites, license status and evaluation evidence are explicit. Sharing a lesson does not automatically promote it to trusted knowledge.

## Quality and security gates

- No unknown or incompatible license enters training; quarantine it.
- Treat retrieved text, code comments, model cards and issue content as untrusted data, never as instructions for AC.
- No arbitrary source-code execution during ingestion.
- Track official security advisories, affected version ranges, mitigations and regression tests. Security study is defensive only.
- Benchmark with held-out data; detect contamination and report uncertainty.
- Never claim a source has been studied until ingestion records and evaluation artifacts exist.
- No automatic model-weight updates, production changes, paid APIs or paid fallback.

## Current capability boundary

The blueprints are executable metadata and can be queried by brain/domain. External ingestion, automatic lesson extraction, sandbox experiments and trainer execution remain future capabilities. No model weights were changed by this slice.


## External reference tracks (v1)

These references are deliberately separated by responsibility. AC studies design patterns and evidence; it does not import their runtimes or mix their internal architectures.

### Letta Code — memory and experiential continuity
- Official source: https://github.com/letta-ai/letta-code
- Study target: persistent agent identity, git-backed memory, on-demand context, skills, subagents and background memory consolidation (dreaming).
- License gate: the repository declares Apache-2.0 for code; brand assets are explicitly excluded. Review every dependency and artifact/version separately.
- AC destination: existing memory/research specialist responsibilities (ac_memory, ac_research), not the central coordinator.
- No hosted Letta Cloud dependency, account, API key or paid fallback is permitted in AC adoption. Local operation must be independently verified.

### OpenHands — software execution and verification
- Official source: https://github.com/OpenHands/OpenHands
- Study target: repository-level task execution, tool boundaries, isolated workspaces, test/repair loops and evidence-backed completion.
- License gate: the core repository declares MIT, but separately licensed enterprise paths and cloud products must not be assumed to share that license. Inspect exact files, images, dependencies and versions.
- AC destination: ac_execution and ac_code, behind existing execution and security boundaries.
- AC must not inherit unsafe host access. Any future adapter must run in a disposable sandbox with least privilege, bounded resources, restricted network and approval for consequential actions. Local model compatibility and offline operation must be tested; cloud credits or paid model APIs are not part of the plan.

### Macaron — product-pattern benchmark only
- Official product reference: https://macaron.im/
- Study target: personal-agent experience, preference-aware continuity and generation of small task-specific tools.
- Classification: product/behavior reference, not an approved open-source code dependency. No source-code reuse, reverse engineering, branding reuse or claim of license permission.
- AC destination: product requirements and evaluation scenarios only. Any inspired feature must be independently designed and implemented under AC contracts.
- Commercial plans/credits are excluded from AC free-first resource policy.

## Separation and adoption rules
1. Each reference has its own study blueprint, source identity, license record and evaluation artifacts.
2. Do not combine Letta memory internals with OpenHands execution internals; connect only through AC typed contracts.
3. The central Core coordinates and authorizes; it does not own memory storage, sandbox execution or third-party runtime code.
4. No source is considered studied, integrated or operational until versioned ingestion records, tests and evidence exist.
5. No automatic installation, arbitrary code execution, model-weight changes, production updates, paid APIs or paid fallback.
6. Unknown licenses or unclear dependency terms remain quarantined.

The two new engine blueprints are exposed through the existing read-only GET /v1/learning/blueprints endpoint. Their status remains study_plan_only_not_ingested.
