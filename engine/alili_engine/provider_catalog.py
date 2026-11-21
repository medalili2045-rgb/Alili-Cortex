"""Free-first provider eligibility catalog with a fail-closed activation gate.

Catalog entries are discovery metadata only. No provider is connected or enabled
by this module. Hosted activation requires fresh, account-specific human evidence.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_CATALOG = Path(__file__).resolve().parent.parent / "data" / "providers.json"
_REQUIRED_HOSTED_CHECKS = (
    "current_free_terms_verified",
    "no_card_requirement_verified",
    "billing_disabled_verified",
    "quota_guard_verified",
    "region_supported_verified",
)


class ProviderCatalog:
    def __init__(self, catalog_path: str | Path | None = None):
        path = Path(catalog_path) if catalog_path else DEFAULT_CATALOG
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("providers"), list):
            raise ValueError("invalid_provider_catalog_schema")
        self.policy = payload.get("policy", {})
        self._providers: dict[str, dict[str, Any]] = {}
        for item in payload["providers"]:
            provider_id = item.get("provider_id")
            if not isinstance(provider_id, str) or not provider_id:
                raise ValueError("provider_id_required")
            if provider_id in self._providers:
                raise ValueError("provider_ids_must_be_unique")
            # Safety invariant: catalog discovery must never activate a service.
            if item.get("enabled_by_default") is not False:
                raise ValueError(f"provider_must_be_disabled_by_default:{provider_id}")
            self._providers[provider_id] = item

    def list(self, *, category: str | None = None, query: str | None = None,
             status: str | None = None, limit: int = 100) -> list[dict]:
        if not isinstance(limit, int) or limit < 1 or limit > 200:
            raise ValueError("invalid_provider_limit")
        category = category.strip().lower() if category else None
        status = status.strip().lower() if status else None
        query = query.strip().lower() if query else None
        result = []
        for item in self._providers.values():
            if category and item.get("category") != category:
                continue
            if status and item.get("review_status") != status:
                continue
            searchable = " ".join((item.get("name", ""), item.get("provider_id", ""),
                                   item.get("description", ""), " ".join(item.get("tags", [])))).lower()
            if query and query not in searchable:
                continue
            result.append(self._public_copy(item))
            if len(result) >= limit:
                break
        return result

    def get(self, provider_id: str) -> dict | None:
        item = self._providers.get(provider_id)
        return self._public_copy(item) if item else None

    def summary(self) -> dict:
        counts: dict[str, int] = {}
        for item in self._providers.values():
            status = item.get("review_status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return {
            "total": len(self._providers),
            "by_review_status": counts,
            "connected": 0,
            "enabled": 0,
            "activation": "disabled_until_account_specific_review",
            "paid_fallback": "prohibited",
            "card_policy": "reject_any_provider_requiring_a_bank_card",
        }

    def activation_decision(self, provider_id: str, evidence: dict | None = None) -> dict:
        item = self._providers.get(provider_id)
        if item is None:
            return {"allowed": False, "provider_id": provider_id, "reason": "provider_not_registered"}
        if item.get("review_status") == "excluded":
            return {"allowed": False, "provider_id": provider_id, "reason": "provider_excluded_by_policy"}
        if item.get("access_type") == "local_software":
            evidence = evidence or {}
            required = ("license_reviewed", "runtime_available")
            missing = [key for key in required if evidence.get(key) is not True]
            return {"allowed": not missing, "provider_id": provider_id,
                    "reason": "local_checks_verified" if not missing else "local_checks_incomplete",
                    "missing_checks": missing}
        evidence = evidence or {}
        missing = [key for key in _REQUIRED_HOSTED_CHECKS if evidence.get(key) is not True]
        if item.get("card_requirement") in ("required", "billing_linked"):
            return {"allowed": False, "provider_id": provider_id, "reason": "bank_card_required_or_linked"}
        if item.get("card_requirement") != "not_required_documented":
            missing.append("card_requirement_not_verified")
        return {"allowed": not missing, "provider_id": provider_id,
                "reason": "all_account_specific_free_checks_verified" if not missing else "hosted_provider_not_verified",
                "missing_checks": missing}

    @staticmethod
    def _public_copy(item: dict) -> dict:
        # Return detached data so API callers cannot mutate the in-memory catalog.
        return json.loads(json.dumps(item))
