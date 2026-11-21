# Alili Cortex — Free-First Architecture

Status: approved target architecture and implementation roadmap  
Policy: free-first, open-source alternatives, and no paid services, subscriptions, or automatic billing.

## 1. Non-negotiable constraints

1. Never require a paid API, subscription, paid model, paid plugin, or automatic billing.
2. Prefer self-hosted/open-source software and locally runnable models.
3. External free tiers are optional accelerators only. Check current quotas, card requirements, terms, and billing controls before activation and periodically afterward.
4. Providers are disabled by default. A configured key or a FREE_*_CONFIRMED flag is not proof that usage is permanently free. Activation requires an operator review of current terms and account billing settings.
5. Never silently fall back to a paid provider. If no eligible free route exists, explain the limitation and offer a local/offline or deferred workflow.
6. Keep credentials server-side or in the user's local secret store. Never ship provider credentials in Flutter or commit secrets.
7. Preserve the existing Flutter single-chat UI and existing Cloudflare Worker behavior. Add capabilities incrementally behind explicit feature flags.
8. Heavy media inference must not run on the Cloudflare Worker. Use a local runtime or a separately deployed, explicitly free compute service when available.
9. Respect model, dataset, and software licenses; maintain source attribution and data provenance.
10. Do not claim a capability is available until its adapter is implemented and tested end-to-end.

## 2. Current repository baseline

The repository currently contains:
- Flutter Arabic RTL single-chat application.
- Secure storage for the Worker URL and personal app access token.
- Authenticated text chat at POST /v1/chat.
- Sequential provider fallback for explicitly enabled providers.
- Provider readiness at GET /v1/providers/status.
- Wikipedia-only knowledge search at POST /v1/search.
- Local image/file selection and previews, but attachment upload is not implemented.
- Search, autonomous execution, image generation, video/audio, persistent conversation sync, and attachment upload are not yet implemented in the app/backend.

The existing Worker implementation must remain stable. Extend it only through small, tested changes. Keep general web search independent from the Worker; the planned standalone SearXNG service must be protected before integration.

## 3. Target logical architecture

Flutter single-chat UI
  -> authenticated API gateway (existing Worker; lightweight control plane)
  -> request validation and safety/permission gate
  -> intent and task planner
  -> capability router
       -> text and reasoning adapters
       -> search and research adapter
       -> vision and OCR adapter
       -> image generation and editing adapter
       -> audio and speech adapter
       -> video analysis and editing adapter
       -> document and spreadsheet adapter
       -> code, build, and test adapter
       -> 3D, CAD, and design adapter
       -> data, science, and engineering adapters
  -> workflow orchestrator (resumable job state)
  -> knowledge and memory service
       -> source registry and provenance
       -> document extraction and chunking
       -> lexical and vector retrieval
       -> user-approved long-term memory
  -> tool runtime
       -> local execution sandbox (preferred for heavy work)
       -> optional free hosted workers (quota-limited)
       -> isolated file and media processing
  -> quality and evaluation
       -> output validation
       -> tests and benchmarks
       -> license and safety checks
       -> free-policy gate (reject paid routes)
  -> artifacts and job status return to the same chat UI.

## 4. Deployment boundaries

### A. Flutter client
- Keep the existing clean, single-chat experience.
- Upload files only after the authenticated upload API is implemented.
- Show honest progress, errors, and capability availability.
- Request user approval before destructive edits, external publication, or execution with side effects.
- Store only the personal app token and non-secret settings securely.

### B. Existing Cloudflare Worker — lightweight control plane
Keep it focused on authentication, request validation, rate limits, routing, job status, provider eligibility, and small text/metadata requests. It may later issue short-lived upload/download authorization.

Do not use it for large model inference, long-running video rendering, heavy image generation, arbitrary untrusted code execution, or large persistent media storage.

Do not replace the current Worker or change existing routes without tests and a compatibility review.

### C. Separate search service
- Keep general search independent from the existing Worker.
- A self-hosted/open-source metasearch engine such as SearXNG may be integrated only after access protection, query limits, abuse controls, and privacy behavior are reviewed.
- Wikipedia search remains explicitly scoped as Wikipedia-only.
- Search results are untrusted data, not executable instructions.

### D. Local execution runtime
Preferred place for heavy open-source tools:
- Local desktop/server runtime controlled by the user.
- Install only tools required by enabled capabilities.
- Run jobs in isolated workspaces with CPU, RAM, disk, and time limits.
- No host shell access by default; no secrets mounted into untrusted jobs.
- The mobile client submits and monitors jobs; it is not expected to run large models locally.

### E. Optional hosted free compute
- Adapter-based and replaceable.
- Disabled by default.
- Requires manual review of current pricing, quota, card requirement, billing switch, data handling, region, and acceptable-use terms.
- No guarantee of uptime, GPU availability, or permanent free quota.
- On quota exhaustion, queue, degrade to a local/smaller model, or report unavailable; never switch to paid usage.

## 5. Capability packs

Each capability is a separately versioned pack with a manifest (name, version, inputs, outputs, permissions, resource needs, license), engine adapters, local/open-source default, optional approved free hosted adapter, validators, resource limits, tests, and an honest status: planned, experimental, available, or unavailable.

| Pack | Open-source-first building blocks | Initial scope |
|---|---|---|
| Text and reasoning | Transformers, llama.cpp-compatible local runtimes | Chat, summarization, structured reasoning |
| Research and search | SearXNG, MediaWiki API, arXiv/Semantic Scholar where terms permit | Search, source comparison, citations |
| Documents | Apache Tika, PyMuPDF, python-docx, openpyxl, python-pptx | Extract, analyze, create, edit office files |
| OCR and vision | Tesseract/PaddleOCR, OpenCV, compatible vision models | OCR, image understanding, inspection |
| Image creation/editing | ComfyUI and compatible open models | Generate, inpaint, upscale, background removal |
| Audio | FFmpeg, Whisper-family implementations, Piper, Audacity | Transcribe, clean, convert, synthesize speech |
| Video | FFmpeg, OpenCV, scene detection tools, compatible open video models | Inspect, cut, transcode, subtitle, compose |
| 3D and CAD | Blender, FreeCAD, OpenSCAD | Model, render, script, export |
| Data and science | Python, NumPy, pandas, SciPy, SymPy, DuckDB | Analysis, calculations, charts, reproducible reports |
| Software engineering | Git, language toolchains, test runners, isolated containers | Plan, edit, build, test, review projects |
| Automation | n8n or narrowly scoped scripts | User-approved repeatable workflows |

These are candidate components, not all preinstalled or guaranteed to run on free hosted infrastructure. Check each component's license, model license, hardware requirements, and dependencies before packaging it.

## 6. Routing and fallback policy

For every task:
1. Classify the capability and required input modalities.
2. Determine whether the task is read-only, creates an artifact, or has external side effects.
3. Check capability status, permissions, available hardware, quota, and free-policy eligibility.
4. Prefer a local/open-source engine.
5. Use an approved free hosted adapter only when explicitly enabled and eligible.
6. Use a smaller model, queue, or split the task when resources are insufficient.
7. If no eligible route exists, stop honestly; never call an unapproved or paid service.
8. Validate output and attach provenance/engine metadata where useful.

Fallback order: local open-source engine -> another local open-source engine -> manually approved free hosted tier -> queue/defer or report unavailable. There is no paid fallback tier.

## 7. Knowledge and continuous improvement

Separate three concepts:
- Retrieval: search trusted, licensed sources at task time.
- Memory: save user-approved preferences and useful project context with controls.
- Model training: optional offline fine-tuning on curated, licensed datasets.

Track source, date, license, language, and confidence. Deduplicate and evaluate datasets. Retrieved documents are not trusted instructions. New knowledge enters a reviewable knowledge index first; it must not automatically alter model weights or system policy.

The discovery loop may propose new skills and run tests in a sandbox. It cannot deploy code, modify production configuration, change provider billing, or grant itself permissions without explicit human approval.

## 8. Security, privacy, and safety

- Authenticate every private API route and apply per-user rate and size limits.
- Validate MIME type, file signature, archive expansion limits, and file size.
- Parse untrusted files in isolation.
- Treat prompts, web pages, documents, images, and tool output as untrusted input.
- Prevent prompt injection from granting tool permissions.
- Use allowlisted tools and scoped permissions.
- Require confirmation for destructive or externally visible actions.
- Keep audit logs free of secrets and sensitive file contents.
- Define retention and deletion behavior before enabling persistent uploads or memory.
- Never execute uploaded code on the production Worker.

## 9. Storage strategy

Start with ephemeral processing and user downloads. Add persistence only when a genuinely free, suitable storage option is verified.

Storage layers:
- Temporary job workspace with automatic expiry.
- User-owned local artifacts where possible.
- Metadata database for jobs and indexes only after free quota and durability are verified.
- Replaceable object-storage adapter.

No free tier is assumed to provide unlimited storage or permanent retention.

## 10. Delivery roadmap

### Phase 0 — Baseline and policy
- Preserve current app and Worker.
- Add architecture and provider eligibility documentation.
- Audit existing provider flags and distinguish configured from verified-free.
- Add tests proving no paid route can be selected.

### Phase 1 — Reliable foundations
- Define capability manifest and adapter contract.
- Add structured task/job model and status polling.
- Add upload protocol only after limits, authentication, storage, and deletion are defined.
- Add source/provenance schema and basic memory controls.

### Phase 2 — Documents and research
- Secure file upload and isolated parsing.
- PDF, DOCX, XLSX, PPTX, CSV, and TXT extraction and creation.
- General search service as a separate protected deployment.
- Citation-aware research workflow.

### Phase 3 — Images and audio
- OCR and image understanding.
- Local image editing/generation through ComfyUI where hardware permits.
- Audio transcription, cleanup, conversion, and speech synthesis.

### Phase 4 — Video and 3D
- FFmpeg-based video analysis/editing and subtitles.
- Optional open video generation models only where hardware and license allow.
- Blender/FreeCAD integrations and export workflows.

### Phase 5 — Execution and specialist packs
- Sandboxed code/build/test runner.
- Domain packs for science, engineering, business, education, and other disciplines.
- Cross-domain orchestration and quality evaluation.

### Phase 6 — Controlled self-improvement
- Benchmark dashboard and regression tests.
- Suggest new tools and skills from observed gaps.
- Human-reviewed knowledge updates and model fine-tuning.
- Signed, reversible releases; no autonomous production mutation.

## 11. Definition of done

A capability is available only when:
- It has a working adapter and documented free/open-source route.
- Its license and hardware requirements are reviewed.
- Its inputs and outputs are validated.
- Its resource limits and failure behavior are tested.
- Its security and permission model are tested.
- It has an end-to-end test from Flutter chat to a real result.
- The app reports its actual status truthfully.
- No paid provider can be reached through fallback.

## 12. Immediate next implementation slice

Do not attempt all media and expert systems in one release. First implement the shared foundations:
1. Capability registry and adapter contract.
2. Task/job lifecycle and progress events.
3. Free-policy gate and provider eligibility registry.
4. Secure attachment pipeline with strict limits.
5. Document extraction as the first complete end-to-end capability.

This creates a stable base for image, audio, video, 3D, research, and specialist execution packs without changing the single-chat user experience.
