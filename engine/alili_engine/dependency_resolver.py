"""AC Dependency Resolver v1: bounded, metadata-only PyPI dependency graph.

This is a conservative resolver, not a package installer. It resolves stable
versions only when every encountered constraint can be evaluated safely.
Unsupported PEP 440 forms fail closed and remain unresolved.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote, urlsplit

_ALLOWED_HOSTS = {"pypi.org", "api.osv.dev"}
_MAX_RESPONSE = 2_000_000
_MAX_NODES = 300
_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
_REQ_RE = re.compile(
    r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[A-Za-z0-9_,.-]+\])?\s*(.*?)(?:\s*;\s*(.*))?$"
)
_SPEC_RE = re.compile(r"(===|~=|==|!=|>=|<=|>|<)\s*([A-Za-z0-9.*+!_-]+)")


class DependencyResolutionError(RuntimeError):
    pass


def normalize_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _request_json(url: str, *, method: str = "GET",
                  payload: dict | None = None,
                  opener: Callable | None = None) -> dict:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in _ALLOWED_HOSTS:
        raise DependencyResolutionError("endpoint_not_allowlisted")
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Accept": "application/json", "User-Agent": "Alili-Cortex-Dependency-Resolver/1.0",
                 **({"Content-Type": "application/json"} if body else {})},
    )
    try:
        with (opener or urllib.request.urlopen)(req, timeout=8) as response:
            final_url = response.geturl() if hasattr(response, "geturl") else url
            final = urlsplit(final_url)
            if final.scheme != "https" or final.hostname not in _ALLOWED_HOSTS:
                raise DependencyResolutionError("redirect_target_not_allowlisted")
            raw = response.read(_MAX_RESPONSE + 1)
    except DependencyResolutionError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise DependencyResolutionError("metadata_fetch_failed") from exc
    if len(raw) > _MAX_RESPONSE:
        raise DependencyResolutionError("metadata_response_too_large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DependencyResolutionError("invalid_metadata_json") from exc
    if not isinstance(value, dict):
        raise DependencyResolutionError("unexpected_metadata_shape")
    return value


def parse_requirement(raw: str) -> dict | None:
    if not isinstance(raw, str):
        return None
    match = _REQ_RE.match(raw)
    if not match:
        return None
    return {"name": match.group(1), "specifier": (match.group(2) or "").strip(),
            "marker": (match.group(3) or "").strip() or None, "raw": raw}


def _version_tuple(version: str) -> tuple | None:
    """Small strict PEP 440 subset; unsupported forms are not guessed."""
    value = version.strip()
    m = re.fullmatch(r"(\d+(?:\.\d+)*)(?:(a|b|rc)(\d+)|\.post(\d+)|\.dev(\d+))?", value, re.I)
    if not m:
        return None
    release = tuple(int(x) for x in m.group(1).split("."))
    tag = (m.group(2) or "").lower()
    if tag:
        phase = {"a": 0, "b": 1, "rc": 2}[tag]
        suffix = int(m.group(3))
    elif m.group(5):
        phase, suffix = -1, int(m.group(5))
    elif m.group(4):
        phase, suffix = 4, int(m.group(4))
    else:
        phase, suffix = 3, 0
    return release, phase, suffix


def _compare_versions(left: tuple, right: tuple) -> int:
    left_release, left_phase, left_suffix = left
    right_release, right_phase, right_suffix = right
    width = max(len(left_release), len(right_release))
    lkey = (left_release + (0,) * (width - len(left_release)), left_phase, left_suffix)
    rkey = (right_release + (0,) * (width - len(right_release)), right_phase, right_suffix)
    return (lkey > rkey) - (lkey < rkey)


def version_satisfies(version: str, specifier: str) -> bool | None:
    """Return None when the specifier is outside the deliberately supported subset."""
    if not specifier:
        return True
    candidate = _version_tuple(version)
    if candidate is None:
        return None
    clauses = [x.strip() for x in specifier.split(",") if x.strip()]
    if not clauses:
        return True
    for clause in clauses:
        m = _SPEC_RE.fullmatch(clause)
        if not m:
            return None
        op, wanted = m.groups()
        if op in {"==", "!="} and wanted.endswith(".*"):
            prefix = wanted[:-2]
            matched = version == prefix or version.startswith(prefix + ".")
            if (op == "==" and not matched) or (op == "!=" and matched):
                return False
            continue
        target = _version_tuple(wanted)
        if target is None:
            return None
        comparison = _compare_versions(candidate, target)
        if op == "===":
            ok = version == wanted
        elif op == "==":
            ok = comparison == 0
        elif op == "!=":
            ok = comparison != 0
        elif op == ">=":
            ok = comparison >= 0
        elif op == "<=":
            ok = comparison <= 0
        elif op == ">":
            ok = comparison > 0
        elif op == "<":
            ok = comparison < 0
        elif op == "~=":
            release, _, _ = target
            upper = release[:-1] + (release[-1] + 1,) if len(release) > 1 else (release[0] + 1,)
            upper_target = (upper, 3, 0)
            ok = comparison >= 0 and _compare_versions(candidate, upper_target) < 0
        else:
            return None
        if not ok:
            return False
    return True


class DependencyResolver:
    def __init__(self, manifest: dict, *, opener: Callable | None = None,
                 max_nodes: int = _MAX_NODES):
        candidates = manifest.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise DependencyResolutionError("invalid_candidate_manifest")
        self.manifest = manifest
        self.opener = opener
        self.max_nodes = max(1, min(int(max_nodes), _MAX_NODES))
        self.roots = {}
        for item in candidates:
            name = item.get("package_name")
            if not isinstance(name, str) or not _NAME_RE.fullmatch(name):
                raise DependencyResolutionError("invalid_manifest_package_name")
            self.roots[normalize_name(name)] = item

    def _pypi(self, name: str) -> dict:
        safe = quote(name, safe="")
        return _request_json(f"https://pypi.org/pypi/{safe}/json", opener=self.opener)

    def _osv(self, name: str, version: str) -> dict:
        try:
            data = _request_json(
                "https://api.osv.dev/v1/query", method="POST",
                payload={"package": {"name": name, "ecosystem": "PyPI"}, "version": version},
                opener=self.opener,
            )
        except DependencyResolutionError:
            return {"status": "unavailable", "count": None, "ids": []}
        vulns = [v for v in (data.get("vulns") or []) if isinstance(v, dict)]
        return {"status": "checked", "count": len(vulns),
                "ids": [v.get("id") for v in vulns if v.get("id")]}

    def resolve(self, *, check_osv: bool = True) -> dict:
        queue = deque()
        nodes: dict[str, dict] = {}
        edges: list[dict] = []
        errors: list[dict] = []
        constraints: dict[str, list[dict]] = {}
        for root in self.roots.values():
            queue.append((root["package_name"], "", "", True))
        while queue and len(nodes) < self.max_nodes:
            name, parent, raw_requirement, is_root = queue.popleft()
            key = normalize_name(name)
            if parent:
                edge = {"from": parent, "to": name, "requirement": raw_requirement}
                if edge not in edges:
                    edges.append(edge)
            parsed = parse_requirement(raw_requirement) if raw_requirement else {
                "name": name, "specifier": "", "marker": None, "raw": ""}
            if parsed is None:
                errors.append({"package": name, "error": "requirement_parse_unsupported"})
                continue
            constraints.setdefault(key, []).append({
                "parent": parent or "AC manifest", "specifier": parsed["specifier"],
                "marker": parsed["marker"], "raw": raw_requirement,
            })
            if key in nodes:
                existing = nodes[key]
                checks = [version_satisfies(existing["version"], c["specifier"])
                          for c in constraints[key]]
                if any(v is False for v in checks):
                    existing["resolution_status"] = "constraint_conflict"
                    existing["unresolved_constraints"] = constraints[key]
                elif any(v is None for v in checks):
                    existing["resolution_status"] = "unsupported_constraint"
                    existing["unresolved_constraints"] = constraints[key]
                continue
            if len(nodes) >= self.max_nodes:
                break
            try:
                metadata = self._pypi(name)
            except DependencyResolutionError as exc:
                errors.append({"package": name, "error": str(exc)})
                nodes[key] = {"name": name, "resolution_status": "metadata_unavailable",
                              "version": None, "license": {"status": "unknown"},
                              "security": {"status": "not_checked"}}
                continue
            info = metadata.get("info") or {}
            version = info.get("version")
            parsed_version = _version_tuple(version) if isinstance(version, str) else None
            if parsed_version is None or parsed_version[1] != 3:
                nodes[key] = {"name": name, "resolution_status": "latest_release_not_stable_or_unsupported",
                              "version": version if isinstance(version, str) else None,
                              "license": {"status": "unknown"},
                              "admission_status": "quarantined", "install_enabled": False}
                errors.append({"package": name, "error": "stable_release_not_confirmed"})
                continue
            returned_name = info.get("name")
            if isinstance(returned_name, str) and normalize_name(returned_name) != key:
                nodes[key] = {"name": name, "resolution_status": "package_identity_mismatch",
                              "version": None, "license": {"status": "unknown"},
                              "admission_status": "quarantined", "install_enabled": False}
                errors.append({"package": name, "error": "package_identity_mismatch"})
                continue
            license_expression = info.get("license_expression")
            license_text = info.get("license")
            classifiers = [x for x in (info.get("classifiers") or [])
                           if isinstance(x, str) and x.startswith("License ::")]
            license_status = "evidence_available_manual_review" if (
                license_expression or license_text or classifiers
            ) else "missing"
            urls = metadata.get("urls") or []
            artifact = next(({
                "filename": u.get("filename"), "sha256": (u.get("digests") or {}).get("sha256"),
                "url": u.get("url"), "downloaded": False
            } for u in urls if isinstance(u, dict) and u.get("yanked") is not True
                and re.fullmatch(r"[a-fA-F0-9]{64}", str((u.get("digests") or {}).get("sha256", "")))), None)
            security = self._osv(name, version) if check_osv else {
                "status": "not_checked", "count": None, "ids": []}
            node = {
                "name": info.get("name") or name,
                "normalized_name": key,
                "version": version,
                "resolution_status": "resolved",
                "root": is_root,
                "requires_python": info.get("requires_python"),
                "license": {
                    "expression": license_expression, "text": license_text,
                    "classifiers": classifiers, "status": license_status,
                    "approved": False,
                },
                "artifact": artifact,
                "security": security,
                "metadata_url": f"https://pypi.org/pypi/{quote(name, safe='')}/json",
                "dependencies": [],
                "admission_status": "quarantined",
                "install_enabled": False,
            }
            nodes[key] = node
            checks = [version_satisfies(version, c["specifier"]) for c in constraints[key]]
            if any(v is False for v in checks):
                node["resolution_status"] = "constraint_conflict"
                node["unresolved_constraints"] = constraints[key]
            elif any(v is None for v in checks):
                node["resolution_status"] = "unsupported_constraint"
                node["unresolved_constraints"] = constraints[key]
            for raw in info.get("requires_dist") or []:
                dep = parse_requirement(raw)
                if dep is None:
                    node["dependencies"].append({"requirement": raw, "status": "unparsed"})
                    continue
                node["dependencies"].append({
                    "name": dep["name"], "specifier": dep["specifier"],
                    "marker": dep["marker"], "status": "queued",
                })
                queue.append((dep["name"], name, raw, False))
        if queue:
            errors.append({"error": "node_limit_reached", "limit": self.max_nodes,
                           "remaining_queue": len(queue)})
        for key, entries in constraints.items():
            if key in nodes:
                nodes[key]["constraints"] = entries
        resolved = sum(1 for n in nodes.values() if n.get("resolution_status") == "resolved")
        unresolved = len(nodes) - resolved
        return {
            "schema_version": "1.0.0",
            "resolver": "AC Dependency Resolver v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "policy": {
                "metadata_only": True, "downloads": False, "installation": False,
                "execution": False, "automatic_approval": False,
                "paid_services_allowed": False, "bank_card_required": False,
                "markers": "recorded_but_all_conditional_dependencies_are_included",
                "pep440": "conservative_subset; unsupported forms fail closed",
            },
            "summary": {
                "root_candidates": len(self.roots), "unique_nodes": len(nodes),
                "resolved_nodes": resolved, "unresolved_nodes": unresolved,
                "dependency_edges": len(edges), "errors": len(errors),
                "fully_resolved": bool(nodes) and unresolved == 0 and not errors,
            },
            "nodes": sorted(nodes.values(), key=lambda n: n["name"].lower()),
            "edges": edges,
            "errors": errors,
        }
