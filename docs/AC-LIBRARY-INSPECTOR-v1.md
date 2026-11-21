# AC Library Inspector v1

## Purpose
Resolve PyPI release metadata for the curated AC Python foundation candidates and create a review report before any acquisition.

## Safety contract
- Network access occurs only when the explicit CLI is run.
- HTTPS endpoints are allowlisted to `pypi.org` and `api.osv.dev`.
- Requests have an 8-second timeout and a 2 MB response cap.
- Package names must exist in `engine/data/library_candidates.json`.
- Only JSON metadata is read. Distribution URLs and SHA-256 values are recorded, but artifact bytes are never downloaded.
- No package is installed, imported, or executed.
- No automatic approval or admission transition occurs.
- Every result remains quarantined, including packages with no OSV findings.
- OSV lookup failure is reported as unavailable, never as a clean security result.
- The report's license fields are upstream metadata evidence, not legal approval.
- Direct dependency requirements are recorded; transitive dependency version and license resolution remains pending.

## Run
From the repository root:

```bash
PYTHONPATH=engine python -m scripts.inspect_library_candidates
```

Skip OSV lookups:

```bash
python -m scripts.inspect_library_candidates --skip-osv
```

Output defaults to `engine/data/library_inspection_report.json`. The command does not seed or mutate the library registry.

## Report review gates
1. Confirm exact release version and upstream project identity.
2. Review release license expression and authoritative license text.
3. Resolve the full transitive dependency graph and review each license.
4. Review OSV findings and upstream security advisories.
5. Verify the chosen distribution hash against an independently retrieved artifact.
6. Test compatibility in an isolated, disposable environment.
7. Only then perform an explicit human approval in AC Library Foundry.

## Limitations
- PyPI's `info` metadata is publisher-provided and may be incomplete.
- The selected artifact SHA-256 is metadata from PyPI; this version does not download the artifact to independently recompute it.
- OSV package-level results do not replace a complete dependency-tree scan.
- A successful inspection does not mean a library is safe, compatible, legally approved, or installed.
