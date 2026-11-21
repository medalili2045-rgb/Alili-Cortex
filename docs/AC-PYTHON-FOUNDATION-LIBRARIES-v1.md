# AC Python Foundation Library Set v1

This is the first curated candidate set for AC Universal Library Foundry. It contains 20 upstream Python projects across application APIs, data, scientific computing, classical ML, model tooling, embeddings, tests, databases, and controlled research ingestion.

## Admission state

Every candidate is quarantined. Version is intentionally `unresolved`; declared license identifiers are discovery hints, not approvals. No packages are installed and no code is imported or executed.

## Review pipeline per candidate

1. Resolve the latest stable release and pin an exact version.
2. Fetch release metadata and source archive from the canonical upstream.
3. Verify the exact license text and any bundled notices for that release.
4. Resolve the full transitive dependency graph and audit every license.
5. Inspect security advisories and project maintenance signals.
6. Compute and persist SHA-256 for the exact source artifact.
7. Run compatibility and isolated tests before approval.
8. Map the accepted package to one or more AC specialist brains.

## Seed into an existing AC SQLite registry

From the repository's `engine` directory:

```bash
python -m scripts.seed_library_candidates --database /path/to/ac-engine.sqlite3
```

The seed operation only adds metadata and leaves every item quarantined. It is idempotent by library ID.

## Candidate set

See `engine/data/library_candidates.json` for canonical repository URLs, declared license hints, specialist mapping, intended purpose, and explicit review gates.

## Free-only policy

No hosted paid API, paid package registry, card-gated service, automatic billing, or auto-installation is used. PyPI and upstream public Git repositories are source references only; availability, exact release versions, and license scope must be rechecked at review time.
