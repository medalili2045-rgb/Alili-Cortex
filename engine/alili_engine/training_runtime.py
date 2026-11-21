"""Offline-only preflight for a future AC local LoRA/QLoRA trainer.

This module hashes local artifacts and checks explicit artifact-level license reviews.
It does not execute training, download data/models, invoke shell commands, or modify weights.
"""
import hashlib
import importlib.util
import json
import platform
import shutil
from pathlib import Path
from urllib.parse import urlparse

REQUIRED_PACKAGES = ("torch", "transformers", "datasets", "peft", "trl")
QLORA_PACKAGES = ("bitsandbytes",)
MAX_DATASET_BYTES = 2 * 1024 * 1024 * 1024
MAX_JSONL_LINE_BYTES = 1024 * 1024
MAX_CHECKPOINT_WEIGHT_BYTES = 64 * 1024 * 1024 * 1024
MIN_FREE_DISK_BYTES = 512 * 1024 * 1024


def _inside_root(path_value: str, root_value: str):
    if not isinstance(path_value, str) or not path_value.strip():
        return None, "path_required"
    try:
        root = Path(root_value).expanduser().resolve()
        candidate = Path(path_value).expanduser()
        if not candidate.is_absolute():
            candidate = root / candidate
        candidate = candidate.resolve(strict=True)
        candidate.relative_to(root)
        return candidate, None
    except FileNotFoundError:
        return None, "path_not_found"
    except (ValueError, OSError):
        return None, "path_outside_allowed_root_or_invalid"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _valid_license_review(review, expected_license_id):
    """Require an artifact-specific human review; a license ID alone proves nothing."""
    if not isinstance(review, dict):
        return False, "artifact_license_review_missing"
    if review.get("status") != "approved":
        return False, "artifact_license_not_approved"
    if review.get("license_id") != expected_license_id:
        return False, "artifact_license_id_mismatch"
    reviewer = review.get("reviewer_id")
    reviewed_at = review.get("reviewed_at")
    evidence_url = review.get("evidence_url")
    parsed = urlparse(evidence_url) if isinstance(evidence_url, str) else None
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 200:
        return False, "license_reviewer_required"
    if not isinstance(reviewed_at, str) or not reviewed_at.strip() or len(reviewed_at) > 80:
        return False, "license_review_timestamp_required"
    if not parsed or parsed.scheme != "https" or not parsed.netloc:
        return False, "license_evidence_https_url_required"
    return True, None


def inspect_training_environment(method="lora"):
    if method not in {"lora", "qlora"}:
        raise ValueError("method_must_be_lora_or_qlora")
    packages = list(REQUIRED_PACKAGES + (QLORA_PACKAGES if method == "qlora" else ()))
    availability = {name: importlib.util.find_spec(name) is not None for name in packages}
    missing = [name for name, present in availability.items() if not present]
    return {
        "method": method,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": availability,
        "missing_packages": missing,
        "dependencies_ready": not missing,
        "cpu_count": __import__("os").cpu_count(),
        "hardware_status": "not_measured",
        "execution": "not_started",
    }


def training_preflight(*, model_id, model_registry, checkpoint_path, checkpoint_license_id,
                       dataset_path, dataset_license_id, method="lora",
                       model_root="./models", dataset_root="./data/datasets",
                       checkpoint_license_review=None, dataset_license_review=None,
                       expected_dataset_sha256=None, expected_checkpoint_sha256=None):
    manifest = model_registry.get(model_id)
    if manifest is None:
        raise ValueError("unknown_ac_model_id")
    if method not in {"lora", "qlora"}:
        raise ValueError("method_must_be_lora_or_qlora")
    for name, value in (("dataset_license_id", dataset_license_id),
                        ("checkpoint_license_id", checkpoint_license_id)):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{name}_required")

    checkpoint, checkpoint_error = _inside_root(checkpoint_path, model_root)
    dataset, dataset_error = _inside_root(dataset_path, dataset_root)
    checkpoint_ok = checkpoint is not None and checkpoint.is_dir()
    dataset_ok = dataset is not None and dataset.is_file() and dataset.suffix.lower() == ".jsonl"
    dataset_samples = 0
    dataset_error_detail = dataset_error
    dataset_sha256 = None
    if dataset_ok:
        try:
            if dataset.stat().st_size > MAX_DATASET_BYTES:
                raise ValueError("dataset_file_size_limit_exceeded")
            with dataset.open("rb") as stream:
                while True:
                    raw_line = stream.readline(MAX_JSONL_LINE_BYTES + 1)
                    if not raw_line:
                        break
                    if len(raw_line) > MAX_JSONL_LINE_BYTES:
                        raise ValueError("dataset_line_size_limit_exceeded")
                    if not raw_line.strip():
                        continue
                    value = json.loads(raw_line.decode("utf-8"))
                    if not isinstance(value, dict) or not any(key in value for key in ("messages", "prompt", "text")):
                        raise ValueError("dataset_rows_need_messages_prompt_or_text")
                    dataset_samples += 1
                    if dataset_samples > 1_000_000:
                        raise ValueError("dataset_sample_limit_exceeded")
            if dataset_samples == 0:
                dataset_ok = False
                dataset_error_detail = "dataset_is_empty"
            else:
                dataset_sha256 = _sha256_file(dataset)
                if expected_dataset_sha256 and dataset_sha256 != expected_dataset_sha256:
                    dataset_ok = False
                    dataset_error_detail = "dataset_sha256_mismatch"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            dataset_ok = False
            dataset_error_detail = str(exc)[:200]

    config_ok = False
    if checkpoint_ok and (checkpoint / "config.json").is_file():
        try:
            config_path = (checkpoint / "config.json").resolve(strict=True)
            config_path.relative_to(checkpoint)
            if config_path.stat().st_size <= 1024 * 1024:
                config = json.loads(config_path.read_text(encoding="utf-8"))
                config_ok = isinstance(config, dict) and bool(config)
        except (OSError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
            config_ok = False

    weight_files = []
    if checkpoint_ok:
        for pattern in ("*.safetensors", "pytorch_model*.bin"):
            for path in checkpoint.glob(pattern):
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(checkpoint)
                    if resolved.is_file() and resolved.stat().st_size > 0:
                        weight_files.append(resolved)
                except (OSError, ValueError):
                    continue
            if weight_files:
                break
    weight_total_bytes = sum(path.stat().st_size for path in weight_files)
    weights_found = bool(weight_files) and weight_total_bytes <= MAX_CHECKPOINT_WEIGHT_BYTES
    checkpoint_hashes = {
        path.name: _sha256_file(path) for path in weight_files
    } if weights_found else {}
    checkpoint_sha256 = None
    if checkpoint_hashes:
        combined = hashlib.sha256()
        for name, digest in sorted(checkpoint_hashes.items()):
            combined.update(name.encode("utf-8"))
            combined.update(digest.encode("ascii"))
        checkpoint_sha256 = combined.hexdigest()
    checkpoint_hash_ok = bool(checkpoint_sha256)
    if expected_checkpoint_sha256 and checkpoint_sha256 != expected_checkpoint_sha256:
        checkpoint_hash_ok = False

    try:
        free_disk = shutil.disk_usage(str(dataset_root)).free
    except OSError:
        free_disk = None
    disk_space_ok = free_disk is not None and free_disk >= MIN_FREE_DISK_BYTES
    dataset_license_ok, dataset_license_error = _valid_license_review(
        dataset_license_review, dataset_license_id.strip())
    checkpoint_license_ok, checkpoint_license_error = _valid_license_review(
        checkpoint_license_review, checkpoint_license_id.strip())

    environment = inspect_training_environment(method)
    checks = {
        "registered_ac_model": True,
        "checkpoint_inside_local_model_root": checkpoint is not None,
        "checkpoint_directory": checkpoint_ok,
        "transformers_config_is_valid_json": config_ok,
        "nonempty_local_weight_file_present": weights_found,
        "checkpoint_weight_hash_computed": checkpoint_hash_ok,
        "expected_checkpoint_hash_matches": not expected_checkpoint_sha256 or checkpoint_sha256 == expected_checkpoint_sha256,
        "dataset_inside_local_dataset_root": dataset is not None,
        "jsonl_dataset_rows_valid": dataset_ok,
        "dataset_hash_computed": bool(dataset_sha256),
        "expected_dataset_hash_matches": not expected_dataset_sha256 or dataset_sha256 == expected_dataset_sha256,
        "dataset_license_human_review_approved": dataset_license_ok,
        "checkpoint_license_human_review_approved": checkpoint_license_ok,
        "minimum_free_disk_space_available": disk_space_ok,
        "training_dependencies_available": environment["dependencies_ready"],
        "no_network_downloads": True,
        "no_shell_execution": True,
        "no_weight_changes": True,
    }
    structural_checks_passed = all(checks.values())
    return {
        "model_id": manifest.model_id,
        "display_name": manifest.display_name,
        "method": method,
        "checks": checks,
        "structural_checks_passed": structural_checks_passed,
        "training_ready": False,
        "status": "structural_preflight_passed_training_not_enabled" if structural_checks_passed else "blocked",
        "checkpoint": {
            "path": str(checkpoint) if checkpoint else None,
            "license_id": checkpoint_license_id.strip(),
            "license_review_error": checkpoint_license_error,
            "error": checkpoint_error,
            "weight_files": checkpoint_hashes,
            "weight_bytes": weight_total_bytes,
            "sha256": checkpoint_sha256,
            "weight_integrity": "hash_computed_reference_not_verified" if checkpoint_hash_ok else "not_verified",
        },
        "dataset": {
            "path": str(dataset) if dataset else None,
            "samples": dataset_samples,
            "license_id": dataset_license_id.strip(),
            "license_review_error": dataset_license_error,
            "error": dataset_error_detail,
            "bytes": dataset.stat().st_size if dataset and dataset.is_file() else None,
            "sha256": dataset_sha256,
        },
        "resources": {
            "minimum_free_disk_bytes": MIN_FREE_DISK_BYTES,
            "free_disk_bytes": free_disk,
            "cpu_count": environment["cpu_count"],
            "memory_status": "not_measured",
        },
        "environment": environment,
        "execution": "not_started",
        "weights_updated": False,
        "next_step": "OS-isolated trainer, measured RAM/CPU/GPU limits, tokenizer checks and reproducible evaluation are still required.",
    }
