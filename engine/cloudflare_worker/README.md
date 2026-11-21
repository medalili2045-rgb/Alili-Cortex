# Alili Cortex Python Worker Preview

This is an isolated preview Worker. It does not replace or modify the live
`alili-cortex` gateway or `alili-cortex-autonomous-worker`.

## Bindings and policy

- `AI`: Cloudflare Workers AI binding.
- `AC_STATE`: existing `alili-cortex-worker-state` D1 database.
- `ALILI_ENGINE_API_TOKEN`: required Worker Secret (never commit its value).
- `ALILI_WORKERS_AI_MODEL`: allowlisted model, defaults to
  `@cf/zai-org/glm-4.7-flash`.
- `ALILI_FREE_PLAN_CONFIRMED`: deliberately `false` in the checked-in config.
  Keep false until the account's actual plan and eligibility are confirmed.
- Paid-provider fallback is disabled in code.

Cloudflare documents Python Workers, D1 bindings, and Workers AI bindings:
- https://developers.cloudflare.com/workers/languages/python/
- https://developers.cloudflare.com/workers/languages/python/ffi/
- https://developers.cloudflare.com/workers-ai/configuration/bindings/
- https://developers.cloudflare.com/workers-ai/platform/pricing/

## Local validation

From the `engine/` directory:

```sh
uv run python -m unittest discover -s tests -v
uv run pywrangler dev --config wrangler.toml
```

The preview health route is `GET /health`. Authenticated routes:
- `GET /v1/brains/runtime`
- `POST /v1/brains/plan`
- `POST /v1/brains/dispatch`
- `GET /v1/brains/dispatches`
- `GET /v1/brains/dispatches/{dispatch_id}`

Use a generated random bearer token of at least 32 characters for local testing.
Do not paste it into GitHub or ChatGPT.

## Remote preview gates (not executed)

The following steps are intentionally manual and must not be run until the
account plan, no-card/no-billing policy, and Worker quota eligibility have been
verified in the Cloudflare dashboard:

1. Create a random API token and add it as a Worker Secret:
   `npx wrangler secret put ALILI_ENGINE_API_TOKEN --config wrangler.toml`
2. Apply only the additive D1 migration:
   `npx wrangler d1 migrations apply alili-cortex-worker-state --remote --config wrangler.toml`
3. Deploy the isolated preview:
   `npx wrangler deploy --config wrangler.toml`
4. Test `GET /health`, then authenticated runtime, plan, and dispatch routes.
5. Only after successful preview validation, design a separate reviewed change
   to connect the existing JavaScript gateway through a Service Binding.

Do not set `ALILI_FREE_PLAN_CONFIRMED=true` unless the account plan and
Workers AI free allocation are verified. Workers AI's free allocation is
10,000 Neurons per day; when exhausted on Workers Free, requests fail rather
than switching to paid billing. See the pricing documentation above.

## Data handling

The migration creates only `ac_brain_dispatches` and two indexes. It does not
alter existing `worker_runs` or `ac_chat_messages` tables. Dispatch objectives,
plans, and model outputs are persisted in D1; do not submit secrets, passwords,
or other credentials as task content.
