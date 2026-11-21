# AC Execution Sandbox v1

## Purpose
A separate, opt-in execution component for small Python tasks. It is not model inference, training, or knowledge ingestion.

## v1 policy
- Python snippets only; no package installation or imports.
- AST allowlist; attribute access and unapproved names/calls are rejected.
- 8,000-character code and input limits; 16,000-character output cap.
- 0.1–5 second caller timeout (default 2 seconds), plus a 3-second CPU limit.
- Minimal child environment; no inherited API tokens or application secrets.
- Temporary working directory deleted after each run.
- File creation is blocked by a zero file-size process limit; no file APIs are exposed.
- No network client or import is exposed by the language policy.
- No paid fallback and no cloud dispatch.

## Security boundary
This v1 runner is **best-effort restriction, not a hardened OS/container sandbox**. AST restrictions and subprocess limits reduce the exposed surface but are not a proof against Python interpreter escapes or kernel vulnerabilities. Do not run hostile multi-tenant code or expose this endpoint publicly. A hardened container/microVM with OS-enforced network, filesystem, memory and process isolation is a separate prerequisite for production use.

## API
- `GET /v1/execution/status` (authenticated)
- `POST /v1/execution/run` (authenticated), JSON: `{"code":"print(sum(range(5)))","input_text":""}`

No provider activation, cloud provisioning, billing, or persistent user-code storage occurs.
