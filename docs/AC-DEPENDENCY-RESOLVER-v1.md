# AC Dependency Resolver v1

## Purpose
Build a transitive dependency graph for the curated AC Python library candidates, accept only a stable latest PyPI metadata version, record package license declarations and artifact hashes, and query OSV for each resolved package.

## Safety and limits
- Metadata-only: no distribution download, install, import, or code execution.
- Network is restricted to HTTPS requests to \`pypi.org\` and \`api.osv.dev\`; redirect targets are checked too.
- Each response is capped at 2 MB and each request has an 8-second timeout.
- Graph is capped at 300 unique packages by default.
- All conditional dependencies are included conservatively; environment markers are recorded but not evaluated.
- The version checker supports a conservative PEP 440 subset. Unsupported syntax is marked unresolved; it is never guessed.
- If a later parent introduces a conflicting constraint, the shared node is marked \`constraint_conflict\`.
- License declarations are publisher metadata, not legal approval. Transitive license review remains a human gate.
- OSV outages are reported as unavailable, not as a clean result.
- All graph nodes remain quarantined and installation remains disabled.
- A PyPI-provided SHA-256 is recorded as metadata only; no independent artifact hash verification occurs here.

## Run
From repository root:

\`\`\`bash
PYTHONPATH=engine python -m scripts.resolve_library_dependencies
\`\`\`

Skip OSV lookups:

\`\`\`bash
PYTHONPATH=engine python -m scripts.resolve_library_dependencies --skip-osv
\`\`\`

Limit graph size:

\`\`\`bash
PYTHONPATH=engine python -m scripts.resolve_library_dependencies --max-nodes 100
\`\`\`

Default report: \`engine/data/dependency_resolution_report.json\`.

## Meaning of a fully resolved graph
A fully resolved graph means every encountered package has a stable metadata version that satisfies the supported constraints, the package identity matches PyPI metadata, and the node limit was not exceeded. It does not mean packages are secure, compatible, legally approved, or installed.

## Next gates
1. Resolve unsupported PEP 440 constraints with a standards-compliant resolver.
2. Evaluate environment markers for each target runtime separately.
3. Verify exact release license text and all transitive license compatibility.
4. Independently download artifacts into quarantine and recompute SHA-256 only after explicit acquisition approval.
5. Run isolated compatibility and security tests before any human approval.
