# Alili Cortex Worker API

This is the first backend slice, written from scratch for this repository. It currently implements public health checks, authenticated provider status, and authenticated text chat with sequential provider fallback.

## Implemented routes

- `GET /` and `GET /health`: public health response.
- `GET /v1/providers/status`: authenticated provider readiness.
- `POST /v1/chat`: authenticated text chat with provider fallback.
- `POST /v1/search`: authenticated Wikipedia knowledge search (up to five results; not general web search).
- `OPTIONS`: CORS preflight.

Other planned routes (run, image, video, files, memory, workflows) are deliberately not advertised as implemented yet.

The search route uses the public MediaWiki API and does not require an API key. It is intentionally described as Wikipedia-only knowledge search, not comprehensive web search.

## Security and free-tier guard

Set `APP_API_KEY` as a Cloudflare Worker secret. Provider credentials must also be Worker secrets. Never put credentials in Flutter, source control, logs, or a public config file.

A provider is unavailable unless both its credential/binding exists and its matching `FREE_<PROVIDER>_CONFIRMED=true` variable is explicitly set. This is a fail-closed operator switch, not a guarantee from the provider that usage can never incur charges. Check current terms, quotas, and billing settings before enabling any provider.

Supported secrets:
- `APP_API_KEY`
- `GEMINI_API_KEY`
- `GROQ_API_KEY`
- `NVIDIA_API_KEY`

Supported free-tier confirmation variables:
- `FREE_GEMINI_CONFIRMED`
- `FREE_GROQ_CONFIRMED`
- `FREE_NVIDIA_CONFIRMED`
- `FREE_CLOUDFLARE_CONFIRMED`

Cloudflare AI requires an `AI` binding in Wrangler. It is disabled unless `FREE_CLOUDFLARE_CONFIRMED=true`.

## Local checks

Requires Node.js 20 or newer. No npm dependencies are needed.

```bash
node --test worker/test/*.test.js
```

## Deploy

From this directory, after installing Wrangler and configuring the Cloudflare account:

```bash
npx wrangler secret put APP_API_KEY
npx wrangler secret put GEMINI_API_KEY
npx wrangler secret put GROQ_API_KEY
npx wrangler secret put NVIDIA_API_KEY
npx wrangler deploy
```

Only add the provider secrets you actually use. Do not enable a free-tier confirmation flag until the provider's current pricing, quota, and billing requirements have been verified. Configure CORS origins narrowly for the actual app/web clients.
