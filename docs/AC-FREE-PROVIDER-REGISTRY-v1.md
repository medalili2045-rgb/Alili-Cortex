# AC Free Provider Eligibility Registry v1

## Purpose

This registry records candidate compute, model, database, storage, hosting, and development providers under AC's strict policy:

- No bank-card requirement.
- No subscriptions, paid upgrades, automatic billing, or paid fallback.
- Unknown card requirements are blocked.
- Hosted providers are disabled until account-specific checks are completed.
- A free quota must have a hard stop; no paid overage is permitted.

## API

The authenticated Python engine exposes:

- `GET /v1/providers` — list the provider catalog.
- `GET /v1/providers?category=compute` — filter by category.
- `GET /v1/providers?q=vector` — search names and tags.
- `GET /v1/providers?status=conditional` — filter review status.
- `GET /v1/providers/{provider_id}` — fetch one provider record.

All routes require the engine Bearer token. `/health` remains public.

## Status meanings

- `candidate`: public documentation suggests a free/no-card path; this is not account approval.
- `conditional`: free offering exists but card, region, phone, billing, or quota eligibility remains unresolved.
- `excluded`: rejected under the current policy or insufficient proof of card-free/no-billing use.

The catalog is discovery metadata only. It does not connect accounts, store credentials, activate cloud resources, or prove that an account is eligible.

## Activation gate

A hosted provider is denied unless all five account-specific checks are explicitly true:

1. Current free terms verified.
2. No bank card required.
3. Billing disabled / no paid route configured.
4. Quota hard-stop verified.
5. Region supported.

Providers marked `required` or `billing_linked` for card requirements are always denied. Unknown card requirements are denied. Local software requires a reviewed license and a verified local runtime.

## Operational safety

- No API route in this slice activates a provider.
- No provider is enabled or connected by default.
- No secrets or account credentials are stored in the catalog.
- Quota exhaustion must stop work, queue it, or return an unavailable state.
- Never silently fall back to a paid provider.
- Recheck official pricing and terms before any future activation; free-tier terms can change.

## Current implementation boundary

This change adds a provider catalog and read-only API. It does not deploy Workers, create database resources, enable R2, connect Kaggle/Colab/Neon/Qdrant, run model inference, or train model weights.
