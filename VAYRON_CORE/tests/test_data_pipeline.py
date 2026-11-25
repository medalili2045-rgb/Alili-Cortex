import gzip
import json

import pytest

from vayron_core.data_pipeline import (
    IngestConfig, LicensePolicy, ingest_text_jsonl, validate_media_manifest,
)


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_streams_filters_deduplicates_and_rolls_shards(tmp_path):
    source = tmp_path / "source.jsonl"
    rows = [
        {"id": "1", "source": "fixture", "license": "CC0-1.0", "language": "ar", "text": "مرحبا"},
        {"id": "2", "source": "fixture", "license": "CC0-1.0", "text": "Hello"},
        {"id": "3", "source": "fixture", "license": "CC0-1.0", "text": "Hello"},
        {"id": "4", "source": "fixture", "license": "UNKNOWN", "text": "blocked"},
        {"id": "5", "source": "fixture", "text": "missing license"},
    ]
    _write_jsonl(source, rows)
    result = ingest_text_jsonl(source, tmp_path / "out", config=IngestConfig(shard_records=1))
    assert result["accepted_this_run"] == 2
    assert result["duplicates_this_run"] == 1
    assert result["rejected_this_run"] == 2
    assert len(result["shards"]) == 2
    assert all(item["sha256"] for item in result["shards"])


def test_resume_does_not_duplicate_committed_records(tmp_path):
    source = tmp_path / "source.jsonl"
    _write_jsonl(source, [
        {"id": "a", "source": "fixture", "license": "CC0-1.0", "text": "one"},
    ])
    out = tmp_path / "out"
    ingest_text_jsonl(source, out)
    again = ingest_text_jsonl(source, out)
    assert again["accepted_this_run"] == 0
    assert again["duplicates_this_run"] == 1


def test_gzip_jsonl_is_supported(tmp_path):
    source = tmp_path / "source.jsonl.gz"
    with gzip.open(source, "wt", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "id": "a", "source": "fixture", "license": "CC0-1.0", "text": "compressed"
        }) + "\n")
    result = ingest_text_jsonl(source, tmp_path / "out")
    assert result["accepted_this_run"] == 1


def test_rejects_oversized_or_invalid_json(tmp_path):
    source = tmp_path / "bad.jsonl"
    source.write_text('{"id":"x","source":"s","license":"CC0-1.0","text":"too long"}\n')
    with pytest.raises(ValueError, match="too large"):
        ingest_text_jsonl(source, tmp_path / "out", config=IngestConfig(max_record_bytes=5))


def test_media_manifest_requires_explicit_license_and_type(tmp_path):
    source = tmp_path / "images.jsonl"
    _write_jsonl(source, [
        {"id": "i1", "source": "museum", "license": "CC0-1.0", "asset_path": "img/a.jpg", "media_type": "image"},
        {"id": "i2", "source": "social", "asset_path": "img/b.jpg", "media_type": "image"},
        {"id": "v1", "source": "archive", "license": "CC0-1.0", "asset_path": "v/a.mp4", "media_type": "video"},
    ])
    result = validate_media_manifest(source, media_type="image")
    assert result["accepted"] == 1
    assert result["rejected"] == 2
