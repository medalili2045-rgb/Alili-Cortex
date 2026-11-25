"""Bounded-memory, provenance-aware JSONL ingestion for Vayron.

This module prepares records; it does not download remote corpora, decode media,
or claim that a license is legally compatible. Callers must configure the
approved license identifiers for their intended use.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, TextIO


DEFAULT_ALLOWED_LICENSES = frozenset({
    "CC0-1.0", "CC-BY-4.0", "MIT", "Apache-2.0",
    "BSD-2-Clause", "BSD-3-Clause", "Unlicense",
})


@dataclass(frozen=True)
class LicensePolicy:
    """Explicit allow-list; unknown and missing licenses are rejected."""

    allowed: frozenset[str] = field(default_factory=lambda: DEFAULT_ALLOWED_LICENSES)

    def accepts(self, license_id: str) -> bool:
        return isinstance(license_id, str) and license_id.strip() in self.allowed


@dataclass(frozen=True)
class IngestConfig:
    shard_records: int = 10_000
    max_record_bytes: int = 2_000_000
    text_field: str = "text"

    def validate(self) -> None:
        if self.shard_records < 1:
            raise ValueError("shard_records must be >= 1")
        if self.max_record_bytes < 1:
            raise ValueError("max_record_bytes must be >= 1")
        if not self.text_field:
            raise ValueError("text_field cannot be empty")


def _open_jsonl(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open("r", encoding="utf-8")


def _iter_records(path: Path, max_record_bytes: int) -> Iterator[dict]:
    with _open_jsonl(path) as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            if len(line.encode("utf-8")) > max_record_bytes:
                raise ValueError(f"record too large at {path}:{line_number}")
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
            if not isinstance(item, dict):
                raise ValueError(f"record must be a JSON object at {path}:{line_number}")
            yield item


def _content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def ingest_text_jsonl(
    input_path: str | Path,
    output_dir: str | Path,
    *,
    policy: LicensePolicy | None = None,
    config: IngestConfig | None = None,
) -> dict:
    """Stream licensed text records into immutable JSONL shards.

    Required fields per record: id, source, license, and the configured text
    field. A persistent SQLite hash index provides exact deduplication without
    keeping the corpus in RAM. Re-running the same input safely skips records
    already committed to the output index.
    """
    source_path = Path(input_path)
    destination = Path(output_dir)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    destination.mkdir(parents=True, exist_ok=True)
    policy = policy or LicensePolicy()
    config = config or IngestConfig()
    config.validate()

    db_path = destination / "dedupe.sqlite3"
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE IF NOT EXISTS seen (digest TEXT PRIMARY KEY)")
    db.commit()

    shard_paths = sorted(destination.glob("text-*.jsonl"))
    shard_index = len(shard_paths)
    shard_count = 0
    accepted = rejected = duplicates = 0
    output_stream = None
    current_tmp = None
    current_final = None
    written_shards: list[str] = []

    def open_shard() -> None:
        nonlocal shard_index, shard_count, output_stream, current_tmp, current_final
        current_final = destination / f"text-{shard_index:06d}.jsonl"
        current_tmp = destination / f".{current_final.name}.tmp"
        output_stream = current_tmp.open("w", encoding="utf-8")
        shard_count = 0

    def close_shard() -> None:
        nonlocal shard_index, output_stream, current_tmp, current_final
        if output_stream is None:
            return
        output_stream.flush()
        os.fsync(output_stream.fileno())
        output_stream.close()
        output_stream = None
        if current_tmp.stat().st_size:
            os.replace(current_tmp, current_final)
            written_shards.append(current_final.name)
            shard_index += 1
        else:
            current_tmp.unlink(missing_ok=True)
        current_tmp = current_final = None

    try:
        for record in _iter_records(source_path, config.max_record_bytes):
            text_value = record.get(config.text_field)
            license_id = record.get("license")
            required_ok = (
                isinstance(record.get("id"), (str, int))
                and bool(str(record.get("id")).strip())
                and isinstance(record.get("source"), str)
                and bool(record.get("source").strip())
                and isinstance(text_value, str)
                and bool(text_value.strip())
            )
            if not required_ok or not policy.accepts(license_id):
                rejected += 1
                continue

            digest = _content_hash(text_value)
            try:
                db.execute("INSERT INTO seen(digest) VALUES (?)", (digest,))
            except sqlite3.IntegrityError:
                duplicates += 1
                continue

            normalized = {
                "id": str(record["id"]),
                "source": record["source"],
                "license": license_id.strip(),
                "license_url": record.get("license_url"),
                "language": record.get("language", "und"),
                "domain": record.get("domain", "general"),
                "text": text_value,
                "content_sha256": digest,
            }
            if output_stream is None:
                open_shard()
            output_stream.write(json.dumps(normalized, ensure_ascii=False) + "\n")
            shard_count += 1
            accepted += 1
            if shard_count >= config.shard_records:
                close_shard()
            if accepted % 1000 == 0:
                db.commit()
        close_shard()
        db.commit()
    except Exception:
        if output_stream is not None:
            output_stream.close()
        if current_tmp is not None:
            current_tmp.unlink(missing_ok=True)
        db.rollback()
        raise
    finally:
        db.close()

    all_shards = sorted(destination.glob("text-*.jsonl"))
    manifest = {
        "format_version": 1,
        "input_name": source_path.name,
        "accepted_this_run": accepted,
        "rejected_this_run": rejected,
        "duplicates_this_run": duplicates,
        "shard_records_target": config.shard_records,
        "shards": [
            {
                "path": item.name,
                "bytes": item.stat().st_size,
                "sha256": hashlib.sha256(item.read_bytes()).hexdigest(),
            }
            for item in all_shards
        ],
        "policy_allowed_licenses": sorted(policy.allowed),
    }
    manifest_tmp = destination / ".manifest.json.tmp"
    manifest_path = destination / "manifest.json"
    manifest_tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(manifest_tmp, manifest_path)
    return manifest


def validate_media_manifest(
    input_path: str | Path,
    *,
    media_type: str,
    policy: LicensePolicy | None = None,
    max_record_bytes: int = 2_000_000,
) -> dict:
    """Validate image/video metadata records without downloading or decoding assets.

    Each record needs id, source, license, asset_path, and media_type. This
    deliberately does not infer permission from public visibility or URLs.
    """
    if media_type not in {"image", "video"}:
        raise ValueError("media_type must be 'image' or 'video'")
    policy = policy or LicensePolicy()
    accepted = rejected = 0
    errors: list[str] = []
    for index, record in enumerate(_iter_records(Path(input_path), max_record_bytes), 1):
        valid = (
            str(record.get("media_type", "")).lower() == media_type
            and isinstance(record.get("id"), (str, int))
            and bool(str(record.get("id")).strip())
            and isinstance(record.get("source"), str)
            and bool(record.get("source").strip())
            and isinstance(record.get("asset_path"), str)
            and bool(record.get("asset_path").strip())
            and policy.accepts(record.get("license"))
        )
        if valid:
            accepted += 1
        else:
            rejected += 1
            if len(errors) < 20:
                errors.append(f"record {index}: missing provenance, path, type, or approved license")
    return {
        "media_type": media_type,
        "accepted": accepted,
        "rejected": rejected,
        "errors": errors,
    }
