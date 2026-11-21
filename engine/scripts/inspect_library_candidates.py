"""Run AC Library Inspector against the approved candidate manifest."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from alili_engine.library_inspector import LibraryInspector


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect PyPI metadata for AC candidates; never download or install"
    )
    parser.add_argument("--manifest", default="engine/data/library_candidates.json")
    parser.add_argument("--output", default="engine/data/library_inspection_report.json")
    parser.add_argument("--skip-osv", action="store_true",
                        help="Skip OSV vulnerability lookup")
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    report = LibraryInspector(manifest).inspect_all(check_osv=not args.skip_osv)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\\n",
                      encoding="utf-8")
    print(json.dumps({
        "output": str(output),
        "inspected": report["inspected"],
        "failed": report["failed"],
        "quarantined": report["inspected"],
        "installations": 0,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
