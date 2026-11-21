"""AC License Intelligence v1: conservative SPDX-expression and graph audit.

This module classifies metadata declarations for human review. It is not legal
advice, does not verify license text, and never approves or installs packages.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

# A deliberately small permissive allowlist. Presence means "candidate for
# review", never automatic approval.
_PERMISSIVE = {
    "0BSD", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC",
    "MIT", "MIT-0", "PSF-2.0", "Unlicense", "Zlib",
}
_COPYLEFT_PREFIXES = (
    "AGPL-", "GPL-", "LGPL-", "EUPL-", "OSL-", "CC-BY-SA-",
)
_COPYLEFT_EXACT = {"MPL-2.0", "EPL-1.0", "EPL-2.0", "CDDL-1.0", "CDDL-1.1"}
_PROPRIETARY = {"LicenseRef-Proprietary", "NONE"}
_TOKEN = re.compile(r"\s*(\(|\)|\bAND\b|\bOR\b|\bWITH\b|[A-Za-z0-9][A-Za-z0-9.+-]*)\s*")


class LicenseExpressionError(ValueError):
    pass


def _tokens(expression: str) -> list[str]:
    result = []
    position = 0
    while position < len(expression):
        match = _TOKEN.match(expression, position)
        if not match:
            raise LicenseExpressionError("unsupported_spdx_expression_syntax")
        result.append(match.group(1))
        position = match.end()
    if not result:
        raise LicenseExpressionError("empty_license_expression")
    return result


class _Parser:
    def __init__(self, tokens: list[str]):
        self.tokens = tokens
        self.index = 0

    def peek(self):
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self):
        value = self.peek()
        if value is None:
            raise LicenseExpressionError("unexpected_end_of_expression")
        self.index += 1
        return value

    def parse(self):
        node = self.parse_or()
        if self.peek() is not None:
            raise LicenseExpressionError("unexpected_spdx_token")
        return node

    def parse_or(self):
        children = [self.parse_and()]
        while self.peek() == "OR":
            self.take()
            children.append(self.parse_and())
        return children[0] if len(children) == 1 else ("OR", children)

    def parse_and(self):
        children = [self.parse_atom()]
        while self.peek() == "AND":
            self.take()
            children.append(self.parse_atom())
        return children[0] if len(children) == 1 else ("AND", children)

    def parse_atom(self):
        if self.peek() == "(":
            self.take()
            node = self.parse_or()
            if self.take() != ")":
                raise LicenseExpressionError("unbalanced_spdx_parentheses")
            return node
        identifier = self.take()
        if identifier in {"AND", "OR", "WITH", ")"}:
            raise LicenseExpressionError("expected_license_identifier")
        if self.peek() == "WITH":
            self.take()
            exception = self.take()
            if exception in {"AND", "OR", "WITH", "(", ")"}:
                raise LicenseExpressionError("invalid_spdx_exception")
            return ("WITH", identifier, exception)
        return ("ID", identifier)


def parse_spdx_expression(expression: str) -> Any:
    if not isinstance(expression, str) or not expression.strip():
        raise LicenseExpressionError("license_expression_missing")
    return _Parser(_tokens(expression.strip())).parse()


def _classify_identifier(identifier: str) -> str:
    if identifier in _PERMISSIVE:
        return "permissive_candidate"
    if identifier in _PROPRIETARY:
        return "proprietary_or_noassertion"
    if identifier in _COPYLEFT_EXACT or identifier.startswith(_COPYLEFT_PREFIXES):
        return "copyleft"
    if identifier.startswith("LicenseRef-"):
        return "custom_license_reference"
    if identifier.startswith("DocumentRef-"):
        return "document_reference"
    if identifier.startswith("CC-"):
        return "creative_commons_non_software"
    return "unknown"


def _evaluate(node: Any) -> dict:
    kind = node[0]
    if kind == "ID":
        identifier = node[1]
        classification = _classify_identifier(identifier)
        return {
            "expression": identifier,
            "identifiers": [identifier],
            "classifications": [classification],
            "risk": classification,
            "review_required": True,
        }
    if kind == "WITH":
        identifier, exception = node[1], node[2]
        base = _classify_identifier(identifier)
        return {
            "expression": f"{identifier} WITH {exception}",
            "identifiers": [identifier],
            "exceptions": [exception],
            "classifications": [base, "license_exception_requires_review"],
            "risk": "exception_requires_manual_review",
            "review_required": True,
        }
    operator, children = node
    evaluated = [_evaluate(child) for child in children]
    identifiers = sorted({item for child in evaluated for item in child["identifiers"]})
    classifications = sorted({item for child in evaluated for item in child["classifications"]})
    if operator == "AND":
        risk = "combined_obligations_requires_compatibility_review"
    else:
        risk = "choice_required_between_alternatives"
    return {
        "expression": operator.join(f"({child['expression']})" for child in evaluated),
        "operator": operator,
        "identifiers": identifiers,
        "classifications": classifications,
        "risk": risk,
        "review_required": True,
        "children": evaluated,
    }


def analyze_license_expression(expression: str | None) -> dict:
    if not isinstance(expression, str) or not expression.strip():
        return {
            "expression": expression,
            "status": "missing",
            "classification": "unknown",
            "identifiers": [],
            "review_required": True,
            "approved": False,
        }
    try:
        evaluated = _evaluate(parse_spdx_expression(expression))
    except LicenseExpressionError as exc:
        return {
            "expression": expression,
            "status": "unparsed",
            "classification": "unknown",
            "identifiers": [],
            "error": str(exc),
            "review_required": True,
            "approved": False,
        }
    classes = evaluated["classifications"]
    if evaluated["risk"] == "permissive_candidate":
        classification = "permissive_candidate"
    elif "copyleft" in classes:
        classification = "copyleft"
    elif "proprietary_or_noassertion" in classes:
        classification = "proprietary_or_noassertion"
    elif "custom_license_reference" in classes or "document_reference" in classes:
        classification = "custom_or_document_reference"
    elif "unknown" in classes:
        classification = "unknown"
    elif "creative_commons_non_software" in classes:
        classification = "non_software_license"
    else:
        classification = evaluated["risk"]
    return {
        **evaluated,
        "status": "parsed",
        "classification": classification,
        "review_required": True,
        "approved": False,
    }


class LicenseIntelligence:
    """Audits a dependency-resolver report; does not mutate its input."""

    def analyze(self, dependency_report: dict) -> dict:
        nodes = dependency_report.get("nodes")
        if not isinstance(nodes, list):
            raise ValueError("invalid_dependency_report")
        audited = []
        counts: dict[str, int] = {}
        findings = []
        for node in nodes:
            if not isinstance(node, dict):
                continue
            license_data = node.get("license") or {}
            expression = license_data.get("expression")
            # Older package metadata may expose only the free-text field.
            source = "license_expression" if expression else "license_text_unparsed"
            result = analyze_license_expression(expression)
            if not expression and license_data.get("text"):
                result["expression"] = None
                result["status"] = "text_only_unparsed"
                result["classification"] = "unknown"
                result["text_present"] = True
            elif not expression and license_data.get("classifiers"):
                result["status"] = "classifiers_only_unverified"
                result["classification"] = "unknown"
                result["classifiers"] = license_data["classifiers"]
            result["source"] = source
            record = {
                "name": node.get("name"),
                "version": node.get("version"),
                "root": bool(node.get("root")),
                "resolution_status": node.get("resolution_status", "unknown"),
                "license": result,
                "admission_status": "quarantined",
                "install_enabled": False,
            }
            audited.append(record)
            classification = result["classification"]
            counts[classification] = counts.get(classification, 0) + 1
            if classification != "permissive_candidate":
                findings.append({
                    "package": node.get("name"),
                    "finding": classification,
                    "reason": result.get("error") or result.get("risk") or result.get("status"),
                })
            else:
                findings.append({
                    "package": node.get("name"),
                    "finding": "permissive_candidate_requires_evidence_review",
                    "reason": "SPDX declaration is metadata only; verify exact release license text and notices",
                })
        unresolved = [
            item for item in audited
            if item["resolution_status"] != "resolved"
        ]
        return {
            "schema_version": "1.0.0",
            "analyzer": "AC License Intelligence v1",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "policy": {
                "candidate_permissive_allowlist": sorted(_PERMISSIVE),
                "automatic_approval": False,
                "automatic_installation": False,
                "default_admission_status": "quarantined",
                "unknown_license_fails_closed": True,
                "copyleft_requires_explicit_compatibility_review": True,
                "and_expression": "all obligations require review",
                "or_expression": "choice required; no automatic selection",
                "license_text_verification": "not_performed",
                "legal_advice": False,
            },
            "summary": {
                "packages_audited": len(audited),
                "classification_counts": dict(sorted(counts.items())),
                "findings": len(findings),
                "unresolved_dependency_nodes": len(unresolved),
                "all_packages_quarantined": all(
                    item["admission_status"] == "quarantined" for item in audited
                ),
                "approval_count": 0,
                "install_enabled_count": 0,
            },
            "packages": sorted(audited, key=lambda item: (item["name"] or "").lower()),
            "findings": findings,
        }
