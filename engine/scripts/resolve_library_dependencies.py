"""Resolve AC curated libraries and transitive PyPI dependencies."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from alili_engine.dependency_resolver import DependencyResolver


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resolve AC dependency metadata only; never download or install"
    )
    parser.add_argument("--manifest", default="engine/data/library_candidates.json")
    parser.add_argument("--output", default="engine/data/dependency_resolution_report.json")
    parser.add_argument("--skip-osv", action="store_true")
    parser.add_argument("--max-nodes", type=int, default=300)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    report = DependencyResolver(manifest, max_nodes=args.max_nodes).resolve(
        check_osv=not args.skip_osv
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print(json.dumps({"output": str(output), **report["summary"],
                      "installed": 0, "downloaded": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
