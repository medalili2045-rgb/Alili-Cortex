# VAYRON_CORE

The independent, provider-agnostic software foundation of **Alili Vayron**.

## Implemented layers

- **Core engine:** capability registry, deterministic bootstrap behavior, and local SQLite memory.
- **18 specialist heads:** THINK_yzn, REASON_yzn, SEARCH_yzn, FLASH_yzn, LEARN_yzn, MEMORY_yzn, CODE_yzn, BUILD_yzn, VISION_yzn, VERIFY_yzn, EVOLVE_yzn, KNOW_yzn, SKILL_yzn, RESEARCH_yzn, SELFTEST_yzn, GUARD_yzn, TOOLMAKER_yzn, CODEAUDIT_yzn. These are routing profiles, not separate trained networks.
- **Orchestration:** task planning, approval flags for sensitive operations, result-structure verification, and review-gated knowledge intake.
- **Tokenizer:** Vayron-owned UTF-8 byte tokenizer, supporting Arabic, English, French and code without a pretrained vocabulary.
- **Neural baseline:** a compact decoder-only causal Transformer implemented directly in PyTorch, initialized from random weights.
- **Training pipeline:** deterministic seed, AdamW, gradient clipping, train/validation split, loss checks, checkpoint save/load, and source/license provenance fields.
- **CI:** GitHub Actions test matrix for Python 3.11 and 3.12, including a tiny CPU training smoke test.

## Install and test

Core only:

    python -m pip install -e ".[dev]"
    python -m pytest -q

Neural training:

    python -m pip install -e ".[dev,train]"
    python -m pytest -q

Tiny local training example (use only a corpus you are legally allowed to train on):

    python scripts/train_smoke.py --data corpus.txt --source "your dataset identifier" --license "exact license or permission" --steps 20

The smoke command creates artifacts/vayron-smoke/vayron-small.pt and a JSON report. It proves only that a small training loop can execute and save/reload a checkpoint.

## Originality and interoperability

Vayron owns its tokenizer baseline, neural-model definition, orchestration contracts, routing, and memory policy. Third-party frameworks may provide tensor kernels, optimization, or optional tooling, but Vayron checkpoints must be trained from Vayron's own initialization and lawful, documented data. Never relabel third-party weights as original Vayron weights.

The core has no mandatory external AI API, paid service, API key, credit card, or billing integration. Optional adapters remain replaceable.

## Important limitations

- The 18 heads currently route requests by transparent keyword matching. They are not 18 trained specialist models.
- The neural model is a deliberately tiny baseline, not a competitive general-purpose assistant. Byte tokenization is robust but inefficient.
- A passing smoke test proves the code path works; it does not prove useful language capability.
- No large corpus has been supplied, no long pretraining run has occurred, and no capable production checkpoint exists yet.
- The VISION_yzn head is a routing profile only; no image encoder is implemented.
- Continuous unattended weight updates are disabled. Knowledge ingestion is reviewed and distinct from model training.

A serious foundation model requires a much larger licensed corpus, robust tokenizer experiments, architecture ablations, scalable compute, long training runs, held-out benchmarks, safety evaluations, and hardware-specific inference optimization.

## Safety

External actions, deployments, deletion, payments, and account changes require explicit permission. No autonomous self-modification or unattended weight updates are enabled.
