# VAYRON_CORE

Independent, provider-agnostic foundation for Alili Vayron.

## Design principles
- Local-first and provider-neutral: no external AI API is required by the core.
- Modular capabilities registered behind stable interfaces.
- Explicit, auditable memory; no silent model-weight training.
- Safe defaults: tools are not executed automatically.
- Free/open-source components only; no paid service or billing integration is enabled.

## Initial foundation
- Capability registry and routing.
- Conversation orchestration with deterministic fallback.
- SQLite-backed memory store.
- Health/status reporting.
- Tests for core behavior.

## Run
Requires Python 3.11+.

```bash
cd VAYRON_CORE
python -m venv .venv
# activate the virtual environment
pip install -e ".[dev]"
pytest
```

The first milestone is a tested software foundation, not a trained foundation model. Original model training, datasets, tokenizer, weights, and compute pipeline are separate milestones and must be added and evaluated explicitly.
