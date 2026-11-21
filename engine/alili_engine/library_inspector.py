"""AC Library Inspector v1: metadata-only, fail-closed PyPI inspection.

No artifacts are downloaded, installed, imported, or executed.
Network access is opt-in at the CLI and restricted to PyPI and OSV HTTPS APIs.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote

_ALLOWED_HOSTS = {"pypi.org", "api.osv.dev"}
_PACKAGE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_DEPENDENCY = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_MAX_RESPONSE = 2_000_000
_USER_AGENT = "Alili-Cortex-Library-Inspector/1.0"


class InspectionError(RuntimeError):
    pass


def _normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _safe_json_request(url: str, *, method: str = "GET",
                       payload: dict | None = None,
                       opener: Callable | None = None) -> dict:
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise InspectionError("endpoint_not_allowlisted")
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url, data=body, method=method,
        headers={"Accept": "application/json", "User-Agent": _USER_AGENT,
                 **({"Content-Type": "application/json"} if body else {})},
    )
    open_url = opener or urllib.request.urlopen
    try:
        with open_url(request, timeout=8) as response:
            raw = response.read(_MAX_RESPONSE + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise InspectionError("metadata_fetch_failed") from exc
    if len(raw) > _MAX_RESPONSE:
        raise InspectionError("metadata_response_too_large")
    try:
        result = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InspectionError("invalid_metadata_json") from exc
    if not isinstance(result, dict):
        raise InspectionError("unexpected_metadata_shape")
    return result


def _extract_dependencies(requires_dist: Any) -> list[dict]:
    dependencies = []
    for requirement in requires_dist or []:
        if not isinstance(requirement, str):
            continue
        match = _DEPENDENCY.match(requirement)
        if match:
            dependencies.append({"name": match.group(1),
                                 "requirement": requirement})
    unique = {(_normalize_name(item["name"]), item["requirement"]): item
              for item in dependencies}
    return sorted(unique.values(), key=lambda item: item["name"].lower())


class LibraryInspector:
    """Inspect only names explicitly present in the AC candidate manifest."""

    def __init__(self, manifest: dict, *, opener: Callable | None = None):
        self.manifest = manifest
        self.opener = opener
        candidates = manifest.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise InspectionError("invalid_candidate_manifest")
        self._candidates = {}
        for candidate in candidates:
            name = candidate.get("package_name")
            if not isinstance(name, str) or not _PACKAGE.fullmatch(name):
                raise InspectionError("invalid_manifest_package_name")
            self._candidates[_normalize_name(name)] = candidate

    def inspect(self, package_name: str, *, check_osv: bool = True) -> dict:
        normalized = _normalize_name(package_name)
        candidate = self._candidates.get(normalized)
        if candidate is None:
            raise InspectionError("package_not_in_ac_allowlist")
        name = quote(candidate["package_name"], safe="")
        metadata = _safe_json_request(
            f"https://pypi.org/pypi/{name}/json", opener=self.opener
        )
        info = metadata.get("info") or {}
        version = info.get("version")
        if not isinstance(version, str) or not version:
            raise InspectionError("pypi_version_missing")
        urls = metadata.get("urls") or []
        usable = [item for item in urls if isinstance(item, dict)
                  and item.get("yanked") is not True
                  and isinstance(item.get("digests"), dict)
                  and re.fullmatch(r"[a-fA-F0-9]{64}",
                                   str(item["digests"].get("sha256", "")))]
        artifact = None
        if usable:
            # Prefer a wheel when available; metadata only, never fetch the file.
            usable.sort(key=lambda item: (not str(item.get("filename", "")).endswith(".whl"),
                                          str(item.get("filename", ""))))
            selected = usable[0]
            artifact = {
                "filename": selected.get("filename"),
                "packagetype": selected.get("packagetype"),
                "url": selected.get("url"),
                "sha256": selected["digests"]["sha256"].lower(),
                "size_bytes": selected.get("size"),
                "downloaded": False,
            }
        license_expression = info.get("license_expression")
        license_text = info.get("license")
        classifiers = info.get("classifiers") or []
        license_classifiers = [x for x in classifiers
                               if isinstance(x, str) and x.startswith("License ::")]
        declared_license = license_expression or license_text or None
        license_status = "evidence_available_manual_review_required" if (
            declared_license or license_classifiers
        ) else "license_evidence_missing"
        dependencies = _extract_dependencies(info.get("requires_dist"))
        osv = {"status": "not_checked", "vulnerability_count": None}
        if check_osv:
            osv = self._check_osv(candidate["package_name"], version)
        return {
            "library_id": candidate["library_id"],
            "package_name": candidate["package_name"],
            "display_name": candidate.get("display_name"),
            "ecosystem": "PyPI",
            "resolved_version": version,
            "version_source": f"https://pypi.org/pypi/{name}/json",
            "release_metadata_url": f"https://pypi.org/pypi/{name}/{quote(version, safe='')}/json",
            "project_urls": info.get("project_urls") or {},
            "summary": info.get("summary"),
            "requires_python": info.get("requires_python"),
            "license": {
                "declared_expression": license_expression,
                "declared_text": license_text,
                "classifiers": license_classifiers,
                "status": license_status,
                "approved": False,
            },
            "dependencies": dependencies,
            "dependency_license_review": "pending_transitive_resolution",
            "artifact": artifact,
            "security": osv,
            "admission_status": "quarantined",
            "install_enabled": False,
            "automatic_approval": False,
            "inspected_at": datetime.now(timezone.utc).isoformat(),
        }

    def _check_osv(self, package_name: str, version: str) -> dict:
        try:
            result = _safe_json_request(
                "https://api.osv.dev/v1/query", method="POST",
                payload={"package": {"name": package_name, "ecosystem": "PyPI"},
                         "version": version},
                opener=self.opener,
            )
        except InspectionError:
            return {"status": "unavailable", "vulnerability_count": None,
                    "details": []}
        vulns = result.get("vulns") or []
        return {
            "status": "checked",
            "vulnerability_count": len(vulns),
            "details": [{
                "id": item.get("id"),
                "summary": item.get("summary"),
                "modified": item.get("modified"),
                "references": [ref.get("url") for ref in item.get("references", [])
                               if isinstance(ref, dict) and ref.get("url", "").startswith("https://")][:5],
            } for item in vulns if isinstance(item, dict)],
        }

    def inspect_all(self, *, check_osv: bool = True) -> dict:
        results, errors = [], []
        for candidate in self.manifest["candidates"]:
            try:
                results.append(self.inspect(candidate["package_name"],
                                            check_osv=check_osv))
            except InspectionError as exc:
                errors.append({"library_id": candidate.get("library_id"),
                               "error": str(exc)})
        return {
            "schema_version": "1.0.0",
            "inspector": "AC Library Inspector v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "policy": {
                "metadata_only": True,
                "downloads": False,
                "installation": False,
                "execution": False,
                "automatic_approval": False,
                "paid_services_allowed": False,
                "bank_card_required": False,
            },
            "inspected": len(results),
            "failed": len(errors),
            "results": results,
            "errors": errors,
        }
