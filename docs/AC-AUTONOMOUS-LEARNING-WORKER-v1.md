# AC Autonomous Learning Worker v1

## Purpose

The autonomous worker is a separate process from the HTTP API. It can run unattended on a host that remains powered on and connected to the internet. By default it starts one bounded study cycle immediately, then repeats every 24 hours.

It is not started automatically by the API server. This prevents multiple API workers from accidentally launching duplicate schedulers.

## Run locally

From the `engine/` directory:

```bash
ALILI_ENGINE_DB_PATH=./data/jobs.sqlite3 python -m alili_engine.autonomous_worker
```

Run one cycle and exit:

```bash
ALILI_ENGINE_DB_PATH=./data/jobs.sqlite3 python -m alili_engine.autonomous_worker --once
```

Inspect, pause or resume:

```bash
ALILI_ENGINE_DB_PATH=./data/jobs.sqlite3 python -m alili_engine.autonomous_worker --status
ALILI_ENGINE_DB_PATH=./data/jobs.sqlite3 python -m alili_engine.autonomous_worker --pause
ALILI_ENGINE_DB_PATH=./data/jobs.sqlite3 python -m alili_engine.autonomous_worker --resume
```

Configuration:
- `--interval-hours 24`: repeat interval (minimum one hour; default 24).
- `--max-documents 3`: maximum changed documents ingested per cycle (1–20).
- `--db-path PATH`: shared SQLite database path. The CLI sets `ALILI_ENGINE_DB_PATH` to this same path for the engine service.

## Always-on deployment

To continue while the user's phone or computer is off, deploy this process on a separate always-on host with persistent storage and outbound HTTPS access. A Linux systemd service is one option:

```ini
[Unit]
Description=Alili Cortex Autonomous Learning Worker
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/opt/Alili-Cortex-Next/engine
Environment=ALILI_ENGINE_DB_PATH=/var/lib/alili-cortex/jobs.sqlite3
ExecStart=/usr/bin/python3 -m alili_engine.autonomous_worker --interval-hours 24 --max-documents 3
Restart=always
RestartSec=30
User=alili-cortex
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=/var/lib/alili-cortex

[Install]
WantedBy=multi-user.target
```

A free hosting plan is suitable only if its current terms permit a continuously running process, persistent storage and outbound HTTPS without sleeping or requiring paid credits. Many free application hosts sleep or impose runtime quotas; those do not satisfy 24/7. This code does not provision a host, register a service, or guarantee that a free host is available. Local operation stops when the host is powered off.

## Cycle and safety

1. Read the curated AC ecosystem catalog.
2. Scan a bounded rotating window of sources (at most three changed documents by default, at most nine source checks).
3. Fetch only catalog-bound official HTTPS sources through the existing connector's DNS/IP pinning, redirect, timeout and content-type checks.
4. Store new text evidence with a content hash and `review_required` license status; evidence remains quarantined.
5. Create a deterministic keyword-triage study session and run structural provenance and relevance checks.
6. Evidence is always stored with `review_required` license status. The study gate blocks it until a separate human license review is completed; the worker does not self-approve licenses or create knowledge proposals from unreviewed material.

ETag/Last-Modified and the connector's full-document SHA-256 avoid repeatedly studying unchanged material, even when stored evidence is truncated to the 64K study limit. Evidence snapshots are reused on retry so a failed session does not duplicate records. SQLite state stores the source cursor, run history and pause state. Cycle failures are recorded as `failed`, not `completed`. The worker emits structured lifecycle messages through Python's standard logging system so a process supervisor can collect them. A lease lock prevents two worker processes from running a cycle simultaneously; an expired lease allows recovery after a crash. Failed sources are recorded and the cursor advances so one unavailable source cannot permanently block the catalog.

## Important limits

- This v1 is autonomous source checking, evidence intake and deterministic study triage. It is not a semantic research model and does not independently prove factual correctness.
- It does not train or update model weights, install packages, execute retrieved code, crawl recursively, or publish knowledge.
- Copilot, AI Studio and Nano Banana are product/documentation study topics only. Their paid or proprietary runtimes are not activated or copied.
- The worker uses only the configured AC SQLite database. Back it up and keep it private.
- Continuous operation depends on the host, network, storage and process supervisor. The source code alone cannot make a powered-off device run.
