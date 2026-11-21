# AC Cloud Adapter v1

## Purpose

Provide a provider-neutral, free-only resource planner for Alili Cortex. The adapter maps task classes to provider categories, evaluates the provider eligibility gate, and applies a durable UTC-day quota hard stop.

## Safety defaults

- No provider network calls are made by this adapter.
- No cloud resources are provisioned.
- No credentials or API keys are stored.
- No provider is enabled or connected by default.
- Unknown card requirements and missing account evidence fail closed.
- A provider must have all account checks verified and an explicit daily quota limit.
- Quota exhaustion blocks work; paid fallback is prohibited.
- Local quota reservations are accounting only and do not dispatch work to providers.

## Supported task classes

`gpu_experiment`, `python_execution`, `inference`, `vector_search`, `database`, `model_catalog`, `object_storage`, `edge_api`, and `app_hosting`.

## API

Authenticated routes:

- `GET /v1/cloud/status`
- `GET /v1/cloud/plan?task=gpu_experiment&units=1`
- `POST /v1/cloud/reservations` with JSON `{"task":"gpu_experiment","units":1}`

The default service configuration contains no account approvals or quota limits, so planning returns unavailable and reservations are rejected. Future operator configuration must be supplied by trusted deployment configuration after account-specific verification; this API does not expose a way to self-approve providers or raise quotas.

## Quota ledger

SQLite stores per-provider UTC-day unit usage. Reservations use an immediate transaction and reject any request that would exceed the configured limit. Usage persists across process restarts. A new UTC date starts a new daily bucket.

## Current implementation boundary

This is a policy and scheduling adapter, not a provider SDK integration. It does not connect to Cloudflare, Kaggle, Colab, Neon, Qdrant, or any external service. Actual dispatch adapters require separate provider-specific implementation and explicit approval.
