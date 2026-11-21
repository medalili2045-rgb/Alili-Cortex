# Cloudflare Engine Bridge Readiness

Updated: 2026-11-21

## Verified deployed topology

- `alili-cortex` is the existing JavaScript API/provider-routing Worker (deployed source version 2.2.0).
- `alili-cortex-autonomous-worker` has a Service Binding named `AC_API` targeting `alili-cortex`, plus a D1 binding named `AC_STATE`.
- Its daily cron is `15 0 * * *` (00:15 UTC).
- A D1 record dated 2026-11-21 00:15:16 UTC confirms the scheduled invocation reached `AC_API /health` and received HTTP 200.
- The autonomous Worker currently performs a connectivity heartbeat and writes a `worker_runs` record. It explicitly does not perform model training, external code execution, or autonomous learning.
- The D1 database contains `worker_runs` and `ac_chat_messages`; it is not yet the Python engine's persistent store.

## Engine integration gap

The Python engine in this repository is not deployed behind the current Worker:

- `engine/alili_engine/api.py` starts a `ThreadingHTTPServer` and requires an `ALILI_ENGINE_API_TOKEN`.
- `engine/alili_engine/model.py` deliberately accepts only an HTTP loopback model endpoint.
- `engine/alili_engine/brain_runtime.py` uses `ThreadPoolExecutor`.
- The current `alili-cortex` Worker exposes its own provider-routing API; its health endpoint does not prove that the Python engine is running.

Cloudflare Python Workers execute under Pyodide. Cloudflare's standard-library documentation states that `threading` and `multiprocessing` can be imported but are not functional due to WebAssembly limitations. Therefore the existing threaded API and local-loopback model client cannot simply be deployed unchanged.

## Safe migration work added

- Added `engine/alili_engine/async_brain_runtime.py`, a separate async/thread-free specialist dispatcher.
- Added `engine/tests/test_async_brain_runtime.py` covering bounded concurrency, isolated specialist contexts, model readiness, partial failures, quality-review gating, and invalid plans.
- Added `engine/alili_engine/cloudflare_workers_ai.py`, a fail-closed async adapter that requires an explicit free-plan confirmation and an allowlisted free model; it has no API-key or paid-provider fallback.
- Added `engine/tests/test_cloudflare_workers_ai.py` for free-policy blocking, allowlist enforcement, normalized inference results, and empty-response handling.
- The existing local `ACBrianRuntime` remains unchanged; this new class is an adapter foundation, not a deployed runtime.
- The new async runtime expects an injected asynchronous model client. The generic Workers AI adapter is connected through an awaited Python FFI wrapper in the isolated preview entrypoint.
- Added `engine/alili_engine/d1_dispatch_store.py`, an async D1 adapter implementing the existing brain-dispatch persistence contract.
- Added additive migration `engine/migrations/0001_ac_brain_dispatches.sql`; it creates only a new dispatch table and indexes and does not alter the existing `worker_runs` or `ac_chat_messages` tables.
- Added `engine/cloudflare_worker/entry.py` with authenticated runtime, planning, dispatch, and dispatch-history routes.
- Added `engine/wrangler.toml` for a separate Worker named `ac-cortex-python-engine-preview`, using Workers AI and the existing D1 database. `ALILI_FREE_PLAN_CONFIRMED` is hard-set to `false`.
- Added D1 adapter tests and expanded Engine CI syntax checks to include the Python Worker entrypoint.
- None of these changes has been deployed; the D1 migration has not been applied, no Worker secret has been written, and the existing production Workers/bindings remain unchanged.

## Security and billing gates

- A read-only settings audit found credential-like values stored as `plain_text` bindings on Workers `alili`, `alili-ai-pro`, `alili-cortex-brin`, and `wild-pine-6a9b`. Treat the affected credentials as exposed and rotate them with their respective providers. Do not copy their old values into source code or logs. Store replacements only as Worker Secrets.
- `alili-cortex` uses secret bindings for its credential-like settings; no plain-text credential binding was found there.
- Cloudflare billing-profile and payment-method reads returned HTTP 403 because the connected OAuth authorization lacks Billing Read permission. Account plan and payment-card status therefore remain unverified.
- No new Worker was deployed, no binding was changed, no secret was written, and no paid service was enabled.

## Next implementation stages

1. Rotate exposed provider credentials and convert any required replacement values to Worker Secrets.
2. Build and test a Cloudflare Workers AI async model adapter with an explicit free-model allowlist and hard no-paid-fallback behavior.
1. Verify the Cloudflare account plan and Workers AI eligibility without enabling billing; the connected OAuth still lacks Billing Read permission.
2. Run the new Engine CI suite and resolve any failures.
3. Apply the additive D1 migration only after plan and data-handling review.
4. Set the API bearer token as a Worker Secret, then deploy the isolated preview Worker.
5. Test health, authentication, planning, real inference, D1 persistence, and dispatch history on the preview.
6. Only after all checks pass, add a separate reviewed Service Binding change to the existing JavaScript gateway.

## Cloudflare references

- [Python Workers](https://developers.cloudflare.com/workers/languages/python/)
- [Python Workers standard library limitations](https://developers.cloudflare.com/workers/languages/python/stdlib/)
- [Python Workers FFI and bindings](https://developers.cloudflare.com/workers/languages/python/ffi/)
- [Workers Free and Paid pricing](https://developers.cloudflare.com/workers/platform/pricing/)
- [Workers AI pricing and free allocation](https://developers.cloudflare.com/workers-ai/platform/pricing/)
