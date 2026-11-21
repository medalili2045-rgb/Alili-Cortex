# Alili Cortex Autonomous Worker

This Cloudflare Worker is a scheduled connectivity bridge to the existing `alili-cortex` API Worker.

## Connections
- `AC_API`: Cloudflare Service Binding to the existing `alili-cortex` Worker. Calls its public `GET /health` endpoint internally, without sending traffic over the public Internet.
- `AC_STATE`: D1 database `alili-cortex-worker-state` for persistent daily heartbeat records.
- Cron: `15 0 * * *` (00:15 UTC / 01:15 Algeria time).

## Scope and safety
- Checks whether the deployed Alili Cortex API is reachable and records its status.
- Does not read or replace API secrets.
- Does not change the existing API Worker.
- Does not execute repository code, run model training, or publish knowledge.
- The Python engine and its autonomous study cycle still require a separately hosted Python runtime and a secured bridge; this Worker is not a substitute for that runtime.

## Test
```bash
node --test test/*.test.js
```
