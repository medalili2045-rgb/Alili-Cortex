# AC Master Multi-Brain Orchestration v1

AC Master is the central coordinator for specialist brains. It plans delegation; it does not impersonate a specialist or dispatch work to an unavailable runtime.

## Operating model

- Detect specialist domains and create separate, bounded assignments.
- Allow eligible assignments to run in parallel after runtime adapters exist.
- Keep each specialist's assignment context isolated; exchange only versioned artifacts and explicit findings.
- Permit disagreements and route conflicts to critical review rather than silently blending them.
- Use AC Reasoning as the integration and critical-review role.
- Apply a quality gate for provenance, consistency, conflicts, permissions, and validation evidence.
- Keep knowledge ingestion reviewable; never equate it with automatic model-weight training.

## Current implementation boundary

The v1 planner returns a multi-brain delegation plan and exposes it through the authenticated engine API. It does not yet execute model calls, spawn workers, or provide concurrent runtime dispatch. Specialist manifests remain non-operational until their runtime and model/provider eligibility are verified. No paid service, bank-card requirement, or paid fallback is permitted.

## API

POST /v1/brains/plan

Example body:

    {"objective":"ابحث عن المصادر ثم برمج التطبيق واختبره","max_brains":6}

The response contains assignments, isolation rules, quality-gate requirements, and an explicit planning_only execution status.