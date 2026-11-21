"""Free-only cloud resource planner and durable quota hard-stop.

This module plans and reserves local quota units only. It never makes provider
network calls, provisions infrastructure, stores credentials, or falls back to
paid services. Hosted providers are unavailable until explicit account checks
and a daily quota limit are injected by trusted application configuration.
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


TASK_CATEGORIES = {
    "gpu_experiment": ("compute",),
    "python_execution": ("local_runtime", "compute"),
    "inference": ("inference", "local_runtime"),
    "vector_search": ("vector_database",),
    "database": ("database",),
    "model_catalog": ("model_catalog",),
    "object_storage": ("object_storage",),
    "edge_api": ("serverless",),
    "app_hosting": ("hosting",),
}


class CloudQuotaLedger:
    """Thread-safe SQLite UTC-day quota ledger with atomic hard stops."""

    def __init__(self, database_path: str):
        self.database_path = database_path
        self._lock = threading.RLock()
        if database_path != ":memory:":
            Path(database_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(database_path, timeout=10, check_same_thread=False,
                                   isolation_level=None)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.execute("""
                CREATE TABLE IF NOT EXISTS ac_cloud_quota_usage (
                    provider_id TEXT NOT NULL,
                    utc_day TEXT NOT NULL,
                    used_units INTEGER NOT NULL CHECK (used_units >= 0),
                    PRIMARY KEY (provider_id, utc_day)
                )
            """)

    @staticmethod
    def utc_day() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def used(self, provider_id: str, *, utc_day: str | None = None) -> int:
        day = utc_day or self.utc_day()
        with self._lock:
            row = self._db.execute(
                "SELECT used_units FROM ac_cloud_quota_usage WHERE provider_id=? AND utc_day=?",
                (provider_id, day)).fetchone()
        return int(row["used_units"]) if row else 0

    def remaining(self, provider_id: str, daily_limit: int, *, utc_day: str | None = None) -> int:
        if isinstance(daily_limit, bool) or not isinstance(daily_limit, int) or daily_limit < 1:
            return 0
        return max(0, daily_limit - self.used(provider_id, utc_day=utc_day))

    def reserve(self, provider_id: str, units: int, daily_limit: int,
                *, utc_day: str | None = None) -> dict:
        if not isinstance(provider_id, str) or not provider_id.strip():
            raise ValueError("invalid_provider_id")
        if isinstance(units, bool) or not isinstance(units, int) or units < 1:
            raise ValueError("invalid_quota_units")
        if isinstance(daily_limit, bool) or not isinstance(daily_limit, int) or daily_limit < 1:
            return {"reserved": False, "reason": "daily_quota_limit_not_configured"}
        day = utc_day or self.utc_day()
        with self._lock:
            self._db.execute("BEGIN IMMEDIATE")
            try:
                row = self._db.execute(
                    "SELECT used_units FROM ac_cloud_quota_usage WHERE provider_id=? AND utc_day=?",
                    (provider_id, day)).fetchone()
                used = int(row["used_units"]) if row else 0
                if used + units > daily_limit:
                    self._db.execute("ROLLBACK")
                    return {"reserved": False, "reason": "free_quota_exhausted",
                            "provider_id": provider_id, "utc_day": day,
                            "used_units": used, "requested_units": units,
                            "daily_limit": daily_limit, "paid_fallback": "prohibited"}
                new_used = used + units
                self._db.execute("""
                    INSERT INTO ac_cloud_quota_usage(provider_id, utc_day, used_units)
                    VALUES (?, ?, ?)
                    ON CONFLICT(provider_id, utc_day)
                    DO UPDATE SET used_units=excluded.used_units
                """, (provider_id, day, new_used))
                self._db.execute("COMMIT")
                return {"reserved": True, "provider_id": provider_id, "utc_day": day,
                        "used_units": new_used, "remaining_units": daily_limit - new_used,
                        "daily_limit": daily_limit, "paid_fallback": "prohibited"}
            except Exception:
                self._db.execute("ROLLBACK")
                raise

    def close(self) -> None:
        with self._lock:
            self._db.close()


class ACCloudAdapter:
    """Select only explicitly verified providers and enforce a hard free quota."""

    def __init__(self, database_path: str, provider_catalog,
                 *, approved_evidence: Mapping[str, dict] | None = None,
                 daily_quota_limits: Mapping[str, int] | None = None):
        self.providers = provider_catalog
        self.approved_evidence = dict(approved_evidence or {})
        self.daily_quota_limits = dict(daily_quota_limits or {})
        self.ledger = CloudQuotaLedger(database_path)

    def status(self) -> dict:
        return {
            "adapter": "ACCloudAdapter",
            "mode": "free_only",
            "provider_network_calls": False,
            "connected_providers": 0,
            "enabled_providers": 0,
            "paid_fallback": "prohibited",
            "default_activation": "blocked_until_account_verification",
            "quota_ledger": "sqlite_utc_daily_hard_stop",
        }

    def plan(self, task: str, *, units: int = 1) -> dict:
        if task not in TASK_CATEGORIES:
            raise ValueError("unsupported_cloud_task")
        if isinstance(units, bool) or not isinstance(units, int) or units < 1:
            raise ValueError("invalid_quota_units")
        categories = TASK_CATEGORIES[task]
        candidates = [item for category in categories
                      for item in self.providers.list(category=category, limit=200)]
        blocked = []
        for item in candidates:
            provider_id = item["provider_id"]
            decision = self.providers.activation_decision(
                provider_id, self.approved_evidence.get(provider_id))
            if not decision["allowed"]:
                blocked.append({"provider_id": provider_id, "reason": decision["reason"]})
                continue
            limit = self.daily_quota_limits.get(provider_id)
            if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
                blocked.append({"provider_id": provider_id, "reason": "daily_quota_limit_not_configured"})
                continue
            remaining = self.ledger.remaining(provider_id, limit)
            if remaining < units:
                blocked.append({"provider_id": provider_id, "reason": "free_quota_exhausted"})
                continue
            return {
                "status": "eligible_not_connected",
                "task": task,
                "provider": item,
                "requested_units": units,
                "daily_limit": limit,
                "remaining_units": remaining,
                "reservation_created": False,
                "provider_network_calls": False,
                "paid_fallback": "prohibited",
            }
        return {
            "status": "unavailable",
            "task": task,
            "requested_units": units,
            "reason": "no_provider_passed_free_only_account_and_quota_checks",
            "blocked_candidates": blocked,
            "paid_fallback": "prohibited",
            "provider_network_calls": False,
        }

    def reserve(self, task: str, *, units: int = 1) -> dict:
        plan = self.plan(task, units=units)
        if plan["status"] != "eligible_not_connected":
            return {"status": "blocked", "plan": plan, "reservation_created": False}
        provider_id = plan["provider"]["provider_id"]
        result = self.ledger.reserve(provider_id, units, self.daily_quota_limits[provider_id])
        if not result["reserved"]:
            return {"status": "blocked", "provider_id": provider_id,
                    "quota": result, "reservation_created": False,
                    "paid_fallback": "prohibited"}
        return {"status": "reserved_locally_not_dispatched", "provider_id": provider_id,
                "quota": result, "reservation_created": True,
                "provider_network_calls": False,
                "notice": "quota_accounting_only_no_external_provider_call"}
