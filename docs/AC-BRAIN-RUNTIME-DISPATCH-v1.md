# AC Brain Runtime & Dispatch v1

## Purpose

Add the first execution adapter between AC Master plans and model inference. It dispatches specialist assignments to an explicitly configured **local loopback model** only.

## What is implemented

- Validates plan shape, registered brain IDs, duplicate assignments, and bounded assignment count.
- Gives each specialist an independent message context and role-specific system guidance.
- Runs up to four assignments concurrently (default: three).
- Uses the existing LocalModelClient; the adapter accepts no hosted provider and has no paid fallback.
- Runs an independent AC Reasoning quality-review call after all specialist calls succeed.
- Reports blocked, partial-failure, completed-pending-review, and completed states separately.
- Does not execute tools, code, deployments, web requests, or modify knowledge.
- Does not claim dedicated specialist weights: specialist roles are prompts routed through one shared local model.

## Runtime prerequisites

Set ALILI_LOCAL_MODEL_URL to an HTTP loopback URL with an explicit port and ALILI_LOCAL_MODEL_NAME to a model actually advertised by that local OpenAI-compatible server. The existing local model client rejects non-loopback endpoints and redirects.

Until the model probe reports ready, dispatch returns blocked and makes no inference calls. No hosted fallback is attempted.

## API/service integration status

The runtime is wired into EngineService and exposed through authenticated GET /v1/brains/runtime and POST /v1/brains/dispatch routes. Dispatch is synchronous and bounded; the dispatch response is not persisted as a job record in this version. The module does not activate any logical brain manifest or change provider eligibility.

## Verification

engine/tests/test_brain_runtime.py covers blocked runtime behavior, isolated dispatch, quality review, invalid brain IDs, duplicate assignments, and partial failures.
