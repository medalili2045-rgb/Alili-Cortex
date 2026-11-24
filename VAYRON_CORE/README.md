# VAYRON_CORE

The independent, provider-agnostic software foundation of **Alili Vayron**.

## Architecture added in this milestone

- **Core engine:** capability registry, deterministic bootstrap behavior, and local SQLite memory.
- **Specialist head router:** THINK_yzn, REASON_yzn, SEARCH_yzn, CODE_yzn, BUILD_yzn, MEMORY_yzn, LEARN_yzn, VISION_yzn, VERIFY_yzn, GUARD_yzn, EVOLVE_yzn, and RESEARCH_yzn.
- **Task planner:** transparent task decomposition with approval gates for sensitive external actions.
- **Verification layer:** structural checks and explicit warnings about what has not been proven.
- **Learning journal:** provenance- and review-gated knowledge records. It does not silently change model weights.
- **CI:** GitHub Actions test matrix for Python 3.11 and 3.12.

## Originality and interoperability

Vayron owns its orchestration contracts, routing, memory policy, and future model interfaces. Open-source libraries may be integrated only after checking their licenses, maintenance, security, hardware requirements, and whether they can run locally. Ideas and public interfaces can inform design; third-party source code, model weights, and datasets are not copied without compatible rights and attribution.

The core has no mandatory external AI API, paid service, API key, credit card, or billing integration. Optional adapters must remain replaceable and must not be required for the local core to start.

## Important current limits

The specialist heads in this milestone are routing profiles, not trained neural networks. The router is deterministic keyword matching. The planner creates transparent task plans; it does not perform language-model reasoning. The verification layer checks plan structure, not factual truth. No original tokenizer, neural architecture, pretrained weights, or trained Vayron model has been created yet.

A genuinely original model requires a defined architecture, lawful training corpus, tokenizer, reproducible training pipeline, suitable compute, checkpoints, evaluations, and safety testing. Memory ingestion is not model-weight training.

## Run locally

Requires Python 3.11+.

    cd VAYRON_CORE
    python -m venv .venv
    # activate the virtual environment
    python -m pip install -e ".[dev]"
    python -m pytest -q

## Safety

External actions, deployments, deletion, payments, and account changes must be separately permissioned and require explicit user approval. No autonomous self-modification or unsupervised weight updates are enabled.
