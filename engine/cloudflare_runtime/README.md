# AC Cloudflare Python Runtime v1

A separate, deployment-gated Python Worker adapter for Alili Cortex. It is
intentionally not the existing `alili-cortex` Worker or the repository's
JavaScript `alili-cortex-api` Worker.

## Included

- Python Worker entrypoint using Cloudflare's `workers` SDK.
- Existing D1 database binding `AC_DB` (read-only health probe until migration).
- Workers AI binding declaration `AI`, but **no AI invocation**.
- Bearer authentication via the out-of-band `AC_ENGINE_API_KEY` Worker secret.
- Additive D1 event migration and bounded event payload validation.
- Catalog-only specialist brain/model endpoints.
- Static safety tests requiring no account credentials or network access.

## Endpoints

- `GET /health` — public liveness only.
- `GET /v1/status` — authenticated D1 connectivity probe.
- `GET /v1/brains` — specialist registry labels; not execution.
- `GET /v1/models` — empty runtime model catalog; not model discovery.
- `POST /v1/inference` — always disabled (503); no Workers AI call.
- `POST /v1/events` — authenticated event write after the migration is applied.

## Local validation

From this directory, with Python 3.13+:

```sh
python -m compileall -q src tests
python -m unittest discover -s tests -v
```

For a real local Worker runtime, install `uv` and Node.js, then run
`uv sync` and `uv run pywrangler dev`. Do not call inference during local
development: Cloudflare documents that Workers AI calls from local development
still access the account and consume usage.

## Deployment gates — all remain closed

1. Confirm the account's actual plan, no-card eligibility, and billing state.
2. Verify current free quota and region eligibility for every bound service.
3. Configure `AC_ENGINE_API_KEY` as a Worker secret; never commit it.
4. Review and explicitly apply `migrations/0001_runtime_events.sql` to D1.
5. Add an enforceable per-day AI quota ledger and verify usage accounting before
   any inference implementation is enabled.
6. Review the deployment diff and target Worker name before deploying.

No deploy, migration, secret write, inference call, paid fallback, or resource
provisioning is performed by this change. The local subprocess sandbox is not
ported: Python Workers do not provide the OS isolation required for that feature.
