# AC Universal Library Foundry v1

## Purpose

A central, auditable admission registry for third-party libraries used by Alili Cortex. The Foundry records identity, version, ecosystem, source provenance, optional source commit, artifact SHA-256 and size, license review state, domain tags, and specialist-brain mapping.

## Safety model

- New entries are quarantined by default.
- Only an explicit, auditable review can approve an entry.
- The initial license allowlist is conservative: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, CC0-1.0, and Unlicense.
- License approval is scoped to the specific artifact class; a source-code license does not grant rights to model weights, datasets, documentation, or other dependencies.
- Unknown, missing, or unsupported licenses remain quarantined.
- Duplicate artifact SHA-256 values are rejected.
- Only known AC specialist brain IDs may be assigned.
- The module does not download, install, import, or execute third-party code.
- No hosted service, API key, payment method, or paid provider is used.

## Engine interface

LibraryFoundry provides register, get, list, review, summary, and fingerprint. The registry uses SQLite and can share the engine's existing persistent database path. Service/API exposure is a separate integration step and must preserve authentication and review gates.

## Artifact fingerprinting

fingerprint(bytes) computes SHA-256 and byte size for an artifact supplied by a trusted local workflow. It does not persist artifact bytes. Artifact storage and secure extraction are intentionally not implemented in v1.

## Approval record

Approval requires a supported SPDX identifier, reviewer identity, HTTPS evidence reference, and an explicit artifact scope. This is an admission control, not legal advice or a substitute for reviewing the exact upstream license text and notices.

## Validation

Run: cd engine && python -m unittest discover -s tests -v

The test suite covers quarantine defaults, explicit approval, unsupported licenses, duplicate hashes, stable fingerprints, brain mapping, invalid sources, and review evidence requirements.

## Current capability boundary

This is a working metadata and governance foundation, not a populated corpus of downloaded libraries. No third-party package has been installed or executed, and no automatic crawler is enabled.
