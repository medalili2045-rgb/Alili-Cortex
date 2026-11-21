# AC License Intelligence v1

## Purpose
Audit every node in an AC Dependency Resolver report, including transitive dependencies, and classify its SPDX license expression for human review.

## Policy
- A small permissive allowlist identifies candidates only; it never approves a package.
- Copyleft, proprietary/no-assertion, custom references, non-software Creative Commons licenses, and unknown identifiers remain quarantined.
- `AND` preserves all combined obligations. `OR` is treated as a choice requiring an explicit documented decision; the analyzer never selects an alternative.
- `WITH` exceptions always require manual review.
- Missing, free-text-only, classifier-only, malformed, and unknown declarations fail closed.
- Every package remains `admission_status=quarantined`; `install_enabled=false`.
- Exact release license text, copyright notices, source provenance, and legal compatibility are not verified by this module. This is not legal advice.

## Run
First generate the dependency graph, then:
```bash
PYTHONPATH=engine python -m scripts.license_intelligence
```
Defaults:
- Input: `engine/data/dependency_resolution_report.json`
- Output: `engine/data/license_intelligence_report.json`

Use `--input` and `--output` to select other report paths.

## Decision boundary
A `permissive_candidate` result means only that the declared SPDX identifier belongs to AC's candidate allowlist. Human reviewers must inspect the exact release's upstream license file and notices, evaluate all transitive dependencies and intended distribution, and record a separate approval. No approval or installation endpoint is provided.
