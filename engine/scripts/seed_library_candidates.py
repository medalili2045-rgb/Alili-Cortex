"""Seed AC's curated candidate manifest into the quarantine-first registry."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from alili_engine.library_foundry import LibraryFoundry


def seed(database_path: str, manifest_path: str) -> dict:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    foundry = LibraryFoundry(database_path)
    inserted, existing, errors = 0, 0, []
    for candidate in manifest["candidates"]:
        if foundry.get(candidate["library_id"]):
            existing += 1
            continue
        try:
            foundry.register(
                library_id=candidate["library_id"],
                name=candidate["display_name"],
                version=candidate["version"],
                ecosystem=candidate["ecosystem"],
                source_url=candidate["source_url"],
                license_id=candidate["license_id"],
                domains=candidate["domains"],
                brains=candidate["brains"],
            )
            inserted += 1
        except (ValueError, TypeError) as exc:
            errors.append({"library_id": candidate.get("library_id"), "error": str(exc)})
    return {"inserted": inserted, "already_present": existing, "errors": errors,
            "registry": foundry.summary()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed AC library candidates in quarantine")
    parser.add_argument("--database", required=True, help="Existing AC engine SQLite database path")
    parser.add_argument("--manifest", default="engine/data/library_candidates.json")
    args = parser.parse_args()
    print(json.dumps(seed(args.database, args.manifest), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
