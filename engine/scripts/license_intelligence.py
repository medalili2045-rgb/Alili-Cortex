"""Audit an AC dependency-resolution report for license declarations."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from alili_engine.license_intelligence import LicenseIntelligence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default="engine/data/dependency_resolution_report.json")
    parser.add_argument("--output", default="engine/data/license_intelligence_report.json")
    args = parser.parse_args()
    source = Path(args.input)
    report = json.loads(source.read_text(encoding="utf-8"))
    result = LicenseIntelligence().analyze(report)
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
