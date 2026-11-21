# AC Master Architecture v1
## Alili Cortex — Independent, Multi-Brain Intelligence System

**Status:** Architecture baseline / proposed implementation contract  
**Version:** 1.0  
**Branch:** docs/ac-master-architecture-v1  
**Compatibility:** Preserve the existing Flutter application and Cloudflare Worker contract until a separately reviewed integration change is ready.

---

## 1. Vision and non-negotiable principles

AC (Alili Cortex) is a user-facing assistant backed by an independently orchestrated intelligence system. It is not a collection of visible model-provider buttons and it is not merely an API proxy.

1. **One assistant, many internal brains.** The user interacts with AC Assistant through one coherent conversation. Internal models, tools, routing and diagnostics remain behind the interface unless the user asks to inspect them.
2. **Maximum practical independence.** Prefer local runtimes, open-weight models, open-source software, portable data and replaceable components. Do not make a hosted provider a required dependency.
3. **Free-first, no surprise billing.** No paid routes, subscriptions, metered APIs, automatic upgrades, or silent cloud fallback. A hosted free tier is disabled by default and may only be enabled after explicit verification of its terms, quotas, billing state and user approval.
4. **Shared learning, controlled propagation.** Brains can exchange knowledge, skills, evidence and evaluation results through governed interfaces. No model may silently overwrite another model's weights, memory or production configuration.
5. **Evidence over claims.** Capabilities have explicit lifecycle states and are advertised as available only after end-to-end tests demonstrate them.
6. **Safe execution by design.** Model output is untrusted. Tool permissions, sandboxing, resource limits, approval gates and audit records are enforced outside the model.
7. **Hardware-aware operation.** Model selection must account for actual CPU, RAM, GPU/VRAM, storage, context length and thermal/power constraints. Do not assume a large model fits the user's device.
8. **Incremental, reversible delivery.** Build behind stable interfaces, test each slice, version artifacts and preserve rollback paths.

## 2. System context

~~~mermaid
flowchart TB
    U[User] <--> UI[AC Assistant - single clean chat]
    UI <--> API[AC Gateway / Session API]
    API <--> MASTER[AC Master Core]
    MASTER <--> ROUTER[Brain Router & Scheduler]
    ROUTER <--> BRAINS[Specialist Brains]
    MASTER <--> MEMORY[AC Memory]
    MASTER <--> KNOWLEDGE[AC Knowledge]
    MASTER <--> TOOLS[Permissioned Tool Gateway]
    TOOLS <--> EXEC[Sandboxed Execution]
    BRAINS <--> BUS[AC Knowledge & Skill Exchange]
    BUS <--> MEMORY
    BUS <--> FOUNDRY[AC Intelligence Foundry]
    FOUNDRY <--> EVAL[Evaluation & Release Gate]
    EVAL --> REG[Model / Skill / Dataset Registry]
    REG --> ROUTER
    POLICY[Free-First Policy & Safety Controls] -. governs .-> API
    POLICY -. governs .-> ROUTER
    POLICY -. governs .-> TOOLS
    POLICY -. governs .-> FOUNDRY
~~~

### 2.1 Main layers

- **Experience:** AC Assistant, one conversation surface, attachment intake, streaming responses and accessible controls.
- **Orchestration:** AC Gateway, session/context assembly, AC Master Core, brain router and workflow coordinator.
- **Intelligence:** specialist brains and replaceable local model runtimes.
- **Knowledge:** conversation memory, long-term user memory, curated knowledge, retrieval indexes, provenance and shared learning artifacts.
- **Action:** permissioned tools, sandbox execution, project builder and verification.
- **Learning:** data preparation, teacher-model adapters, training jobs, benchmark suites, model registry and release gates.
- **Governance:** free-first policy, privacy, security, approval rules, audit log, licensing and capability status.

## 3. AC Assistant — the single user-facing assistant

AC Assistant is the stable personality and interaction contract of the product. It is not required to be a separate foundation model. It uses AC Master and specialist brains behind a single consistent interface.

Responsibilities:
- Understand the user's intent and conversation context.
- Ask for clarification only when a missing detail materially blocks safe progress.
- Explain plans and meaningful limitations in plain language.
- Use tools and specialist brains through the Master Core, not by bypassing policy.
- Maintain consistent tone and response format even when the underlying model changes.
- Distinguish verified results, estimates, proposals and unavailable capabilities.
- Request approval before external, destructive, costly, privacy-sensitive or production-impacting actions.
- Respect user controls for memory, retention, attachments and execution.

The UI remains a clean single-chat experience. Internal model names and orchestration traces are hidden by default; optional diagnostics may be exposed only through a deliberate advanced view.

## 4. AC Master Core — central coordination

AC Master Core owns orchestration, not every specialist skill.

Responsibilities:
- Build a structured task representation from the user's request.
- Decide whether a task needs one brain, multiple brains, retrieval, a tool, or clarification.
- Create a bounded plan with dependencies, expected outputs and verification criteria.
- Route work based on capability, quality evidence, availability, license approval and device resources.
- Coordinate parallel work only when tasks are independent and resource budgets allow it.
- Resolve disagreement using evidence, tests and explicit confidence—not majority vote alone.
- Consolidate results into one assistant response.
- Enforce deadlines, token/context budgets, cancellation and retry limits.
- Record task state and provenance.

The Master must not:
- Treat model-generated text as authorization.
- Claim a task completed merely because a plan was generated.
- Silently enable a remote provider or paid service.
- Publish unreviewed model weights, memory, code or configuration.
- Suppress uncertainty or contradictory evidence.

## 5. AC Multi-Brain — specialist capability domains

A brain is a logical specialist with a declared contract. It may be implemented by a dedicated model, a shared base model with a LoRA adapter, a deterministic toolchain, or a combination. A separate large model per brain is not a requirement.

Initial logical brains:

| Brain | Primary responsibility | Typical collaborators |
|---|---|---|
| AC Reasoning | Logic, decomposition, critique and problem solving | Master, Science, Code |
| AC Code | Software design, implementation and debugging | Execution, Reasoning |
| AC Science | Mathematics, science and engineering reasoning | Research, Reasoning |
| AC Research | Source discovery, extraction, comparison and synthesis | Knowledge, Science |
| AC Vision | Image understanding, OCR and visual inspection | Media, Research |
| AC Media | Audio/video understanding and media workflows | Vision, Execution |
| AC Language | Multilingual communication, translation and language tasks | Assistant, Research |
| AC Strategy | Planning, business and decision analysis | Research, Reasoning |
| AC Execution | Controlled project and tool execution | Code, Master |
| AC Memory | Context retrieval, summarization and memory operations | All brains through governed APIs |

Specialist contract (minimum):
- stable brain ID and version;
- supported task types and input/output schema;
- model/runtime or toolchain reference;
- license and provenance record;
- minimum resource profile;
- capability lifecycle state;
- benchmark results and known limitations;
- data access and tool permission scopes;
- timeout, cancellation and output-size limits.

A specialist may recommend another brain, but only the Master Router schedules it. Brains do not directly spawn unlimited agents.

## 6. AC Knowledge & Skill Exchange — shared learning between brains

This is the common exchange fabric, not an unrestricted shared scratchpad.

### 6.1 Exchangeable artifacts

Brains may publish versioned artifacts such as:
- sourced facts and concise evidence summaries;
- solution methods, algorithms and reusable skills;
- code snippets or patches with tests and licenses;
- task plans and execution traces scrubbed of secrets;
- error patterns and validated corrections;
- benchmark cases and evaluation results;
- domain ontologies, schemas and relationships.

Every artifact must include:
- artifact ID, type, version and creation time;
- originating brain and model/version;
- source references and license/provenance;
- confidence and verification status;
- applicable domain and scope;
- sensitivity classification and retention policy;
- validation tests or reviewer record where applicable.

### 6.2 Controlled propagation lifecycle

**PROPOSED → QUARANTINED → VALIDATED → APPROVED → PUBLISHED → MONITORED**

Rejected or stale artifacts move to **REJECTED** or **SUPERSEDED**; they are not silently deleted from audit history.

- Untrusted teacher outputs and external documents enter quarantine.
- Research claims require traceable sources; critical claims should be corroborated.
- Code and executable artifacts require static checks and sandbox tests.
- Conflicting knowledge is retained as a conflict with provenance, not flattened into a false consensus.
- Sensitive user data is excluded from cross-brain training by default.
- Only approved artifacts enter shared retrieval indexes or training datasets.
- Rollback can revoke a published artifact or restore a previous approved version.

### 6.3 Shared knowledge is not shared weights

The initial implementation shares verified artifacts and retrieval results, not automatic live weight updates. Weight sharing, distillation or adapter merging is a separate training/release process with license checks, benchmark gates and human approval.

## 7. AC Memory and Universal Knowledge

Keep separate stores with separate access and retention rules:

1. **Session context:** current conversation and task state; bounded and short-lived.
2. **User memory:** user-approved preferences and durable project context; inspectable and controllable.
3. **Project memory:** repository decisions, architecture records, issue history and project artifacts.
4. **Knowledge library:** curated public/open materials with source, license and version metadata.
5. **Execution memory:** task plans, logs and test evidence, with secrets redacted.
6. **Training corpus:** only explicitly eligible, licensed and quality-filtered material.

Retrieval should return evidence chunks with provenance, timestamps and source identifiers. The model must be able to say when evidence is missing or stale. Memory deletion/retention controls must be respected across derived indexes and caches.

## 8. AC Intelligence Foundry — training and improvement

Foundry is a controlled offline/queued learning pipeline, not a self-modifying production loop.

Pipeline:
1. **Discover:** identify candidate open-weight models, datasets, code and teaching resources.
2. **License review:** record exact license, use restrictions, attribution and redistribution obligations.
3. **Acquire:** download only approved artifacts from trustworthy sources; verify checksums.
4. **Prepare:** deduplicate, normalize, filter, redact personal data and preserve provenance.
5. **Teacher generation:** optionally obtain demonstrations or critiques from permitted teacher models.
6. **Validate:** use deterministic checks, independent references, expert review where needed and contamination checks.
7. **Train:** begin with retrieval and prompt/tool improvements; use LoRA/QLoRA or distillation only when resources and licenses allow.
8. **Evaluate:** compare against frozen baselines and held-out tests for quality, safety, regressions and resource use.
9. **Release candidate:** package model/adapter, dataset lineage, config and benchmark report.
10. **Approve and deploy:** explicit approval, staged rollout, monitoring and rollback.

Training priority:
- first build high-quality retrieval, tool contracts, evaluation and curated data;
- then fine-tune a suitable open-weight base model for the target hardware;
- use multiple specialist adapters or small specialist models where this beats one oversized model;
- consider training a foundation model from scratch only if a realistic compute, data, budget and maintenance plan exists.

Teacher-model outputs are not ground truth. They must be checked, and teacher licenses/terms must permit the intended distillation or derivative use.

## 9. Model and runtime strategy

- Define a provider-neutral model interface: generate, optional embeddings, health, capabilities and resource profile.
- Keep model weights, adapters, tokenizers and runtime versions in a manifest/registry; do not commit large weights to the application repository by default.
- Prefer local inference through a replaceable runtime adapter.
- Route to the smallest model that meets quality and safety requirements.
- Support quantized models where appropriate, while measuring quality loss.
- Keep hosted inference disabled by default. No automatic fallback from local to cloud.
- A model is not considered operational until a real supported runtime and model have passed smoke, quality, latency and memory tests on target hardware.

Candidate models are evaluated individually; “open source” is not a sufficient license classification. Record whether the release provides weights, code, training data, dataset recipes and commercial-use rights separately.

## 10. AC Execution and Project Builder

Execution is an explicit permissioned service, not an unrestricted capability of the language model.

Required controls:
- isolated workspaces per task;
- no host filesystem access outside approved mounts;
- network disabled by default, with allowlisted access only when required;
- CPU, memory, disk, process, time and output limits;
- read/write scopes and explicit approval for destructive changes;
- secret redaction and no credentials in prompts/logs;
- immutable audit events for tool calls and results;
- test/build/verification evidence before a task is marked complete;
- human approval before production deploys, merges, publishing or external side effects.

Initial workflow states: **requested → planned → awaiting_approval (if needed) → running → verifying → completed | failed | cancelled**. A plan is never a completed task.

## 11. Free-first, privacy and safety policy

Policy decision is fail-closed:
- **local_builtin:** allowed when safe and within local resource limits.
- **local_open_source:** allowed only after license and artifact verification.
- **hosted_free:** disabled unless the operator verifies free terms, quota, billing disabled, data handling and explicitly enables it.
- **paid, subscription, metered_paid, unknown or unverified:** denied.

Additional controls:
- no credit-card requirement accepted as proof of free use;
- no hidden billing activation or usage-based fallback;
- local-only mode must remain usable without network access for supported functions;
- network access is a separate capability and must be explicit;
- encrypt secrets at rest where supported and never commit them;
- minimize personal data, define retention and support deletion;
- treat documents, retrieved text, tool output and model responses as untrusted input;
- prompt injection must not override system policy, tool permissions or user approval requirements.

## 12. Capability lifecycle and truthful status

Every capability uses one of:
- **planned:** designed but not implemented;
- **experimental:** implemented but not sufficiently validated;
- **available:** passed defined end-to-end tests on a documented supported profile;
- **degraded:** partially unavailable or failing health/quality thresholds;
- **disabled:** intentionally unavailable by policy or operator choice.

The capability registry must include evidence, version, supported hardware/runtime and last successful validation. UI claims must be generated from this registry rather than hard-coded promises.

## 13. API and module boundaries

Recommended internal modules (names are logical boundaries; implementation may evolve):
- assistant: conversation contract, response composition and user interaction policy.
- core: task model, planning, orchestration and lifecycle.
- router: brain selection, budgets, concurrency and cancellation.
- brains: specialist contracts and implementations.
- models: local runtimes, model manifests and adapters.
- memory: session, user, project and retrieval stores.
- knowledge: provenance, artifact exchange, validation and versioning.
- learning: datasets, training jobs, evaluation and release gates.
- execution: sandbox, tool gateway, permissions and audit.
- policy: free-first, privacy, safety and approval rules.
- observability: health, metrics, traces and diagnostics with secret redaction.

Core data contracts should be versioned and validated at boundaries. Modules communicate through explicit interfaces/events rather than importing each other's private implementation details.

## 14. Delivery roadmap

### Phase A — Architecture and contracts
- Publish this architecture baseline.
- Define typed schemas for tasks, brains, artifacts, model manifests, policies and capability status.
- Define threat model, privacy model and hardware profiles.
- Preserve current Flutter and Worker contracts.

### Phase B — Reliable central orchestration
- Add conversation/session context assembly around the existing local model adapter.
- Add Master task lifecycle, routing interface and capability-aware scheduling.
- Add cancellation, bounded retries, budgets and audit events.
- Keep deterministic fallback planning local; do not claim model reasoning if no model is configured.

### Phase C — Memory and knowledge exchange
- Add provenance-aware retrieval and separate memory stores.
- Implement the artifact lifecycle and shared knowledge API.
- Add conflict handling, revocation and retention controls.
- Test that unapproved artifacts cannot affect trusted retrieval or training.

### Phase D — First useful specialist brains
- Start with Reasoning, Code, Research and Execution as logical specialists.
- Reuse a base model where practical; add adapters/tools only when benchmarks justify them.
- Implement brain contracts, resource manifests and routing tests.

### Phase E — Foundry and measurable learning
- Add license registry, dataset lineage and training/evaluation jobs.
- Build frozen benchmark suites and held-out evaluation.
- Add candidate model/adapter packaging, approval and rollback.
- No automatic production weight updates.

### Phase F — Multimodal and wider domains
- Add Vision/OCR, Language, Science, Media and Strategy capabilities incrementally.
- Each capability requires its own license, resource, quality and safety validation.
- Integrate with Flutter only after stable API contracts and end-to-end tests.

## 15. Definition of done for the architecture baseline

This document is a design contract, not proof that all described systems exist. The architecture is ready to guide implementation when:
- module and data contracts are agreed and versioned;
- every brain declares its capability, resources, license and permissions;
- cross-brain artifacts carry provenance and pass validation before publication;
- shared knowledge cannot silently alter model weights;
- paid and unknown routes are denied by automated tests;
- execution is isolated and approval-gated;
- model and capability status reflects real tests;
- the assistant remains one coherent user-facing experience;
- no changes are merged into main without explicit user approval.

---

## 16. Current repository baseline and implementation honesty

At the time this architecture is authored, the repository already contains an independent Python engine foundation on the feat/hybrid-core-foundation branch: a deterministic planner, SQLite task lifecycle, capability registry, fail-closed free-first policy, authenticated HTTP API and an experimental loopback-only OpenAI-compatible local model adapter.

That foundation does **not** yet constitute the complete Master Core, Multi-Brain runtime, shared knowledge exchange, long-term memory, training factory, sandbox executor or multimodal system. The Flutter application is not yet integrated with the engine. These remain future implementation slices and must be marked accordingly until tested.
