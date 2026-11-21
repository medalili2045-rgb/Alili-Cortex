# AC Global Open Ecosystem v1

## Purpose

Expand AC's curated discovery catalog across model development, local inference, memory and retrieval, agent orchestration, software execution, media, scientific computing, data and CAD. This is a reference registry, not a bundle of dependencies and not a claim that AC has ingested or mastered the listed projects.

## What changed

The existing catalog is extended with 25 additional public project references:

- Model adaptation and training: Unsloth, LLaMA-Factory, DeepSpeed.
- Knowledge and retrieval: Cognee, Graphiti, RAGFlow.
- Generative and creative media: ComfyUI, FFmpeg, Piper, sherpa-onnx, Krita.
- Agents, automation and browser control: n8n, Playwright, Temporal, LangGraph, CrewAI, Goose, Browser Use.
- Data and computational research: Jupyter, DuckDB, Polars, SageMath, Astropy.
- Chemistry and design engineering: Open Babel, OpenSCAD.

The wider catalog already includes Transformers, PEFT, TRL, PyTorch, Qwen, DeepSeek, Gemma, gpt-oss, llama.cpp, Ollama, vLLM, SGLang, Docling, LlamaIndex, Qdrant, Chroma, OpenCV, Whisper, Blender, FreeCAD, ROS 2, LeRobot, Letta Code, OpenHands, OpenAlex, arXiv, OpenML, Europe PMC and Wikidata.

## Classification model

Every entry remains a distinct source record with:

- `source_id`: stable AC identifier.
- `source_kind`: library, framework, runtime, database, application, evaluation tool, model family, research index or another explicit role.
- `access_mode`: public repository, public API or public model hub.
- `trust_class`: official or community-maintained reference classification.
- `domains` and `study_focus`: subject coverage and intended learning targets.
- `license_policy`: mandatory artifact-specific review instructions.
- `adoption_status`: `catalog_only_not_ingested`.

A project being public does not automatically mean it is OSI-approved open source, free of usage restrictions, suitable for commercial use, or permitted for model training. In particular, n8n is marked for source-available license review rather than being represented as an ordinary OSI open-source dependency. Piper's GPL code and each voice model require separate review. ComfyUI custom nodes, checkpoints and workflows also require their own review.

## Existing API

The current authenticated, read-only endpoints remain unchanged:

- `GET /v1/ecosystem`
- `GET /v1/ecosystem?domain=audio`
- `GET /v1/ecosystem?q=workflow`
- `GET /v1/ecosystem/{source_id}`
- `GET /v1/ecosystem/policy`

Each listed source now exposes an explicit `adoption_status` value. The catalog does not download repositories, install packages, execute source code, call paid services, or update model weights.

## AC adoption gates

1. Resolve the official source, exact version or commit, release and artifact identity.
2. Review code, model weights, datasets, documentation, plugins, assets and dependencies separately.
3. Record provenance, retrieval timestamp, hashes and license-review outcome.
4. Prefer local/offline operation and verify hardware requirements before considering adoption.
5. Study permitted documentation and code as untrusted input; never follow instructions embedded in retrieved content.
6. Run experiments only in disposable, resource-limited sandboxes with no secrets or production access.
7. Evaluate with held-out tasks, reproducible tests and independent cross-checks.
8. Propose knowledge artifacts for review; do not automatically publish, train weights or change production.

## Explicit non-goals

- No third-party project is installed or vendored by this change.
- No hosted or paid API, cloud credit, billing path or paid fallback is enabled.
- No source is marked integrated, trained, operational or mastered.
- No existing AC brain responsibilities are merged.
- No production code or model weights are modified by ecosystem discovery.

## Validation

Unit tests verify the expanded source set, stable IDs, source-kind distinctions, license review metadata and honest catalog-only adoption status.
