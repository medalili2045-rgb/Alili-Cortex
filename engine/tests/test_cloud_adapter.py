import os
import tempfile
import unittest

from alili_engine.cloud_adapter import ACCloudAdapter, CloudQuotaLedger
from alili_engine.provider_catalog import ProviderCatalog


class CloudQuotaLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp.name, "quota.sqlite3")
        self.ledger = CloudQuotaLedger(self.db_path)

    def tearDown(self):
        self.ledger.close()
        self.temp.cleanup()

    def test_quota_reservation_has_atomic_hard_stop(self):
        first = self.ledger.reserve("test-provider", 3, 5, utc_day="2026-11-21")
        second = self.ledger.reserve("test-provider", 2, 5, utc_day="2026-11-21")
        third = self.ledger.reserve("test-provider", 1, 5, utc_day="2026-11-21")
        self.assertTrue(first["reserved"])
        self.assertTrue(second["reserved"])
        self.assertFalse(third["reserved"])
        self.assertEqual(third["reason"], "free_quota_exhausted")
        self.assertEqual(third["paid_fallback"], "prohibited")

    def test_quota_persists_across_ledger_instances(self):
        self.assertTrue(self.ledger.reserve("test-provider", 2, 4, utc_day="2026-11-21")["reserved"])
        other = CloudQuotaLedger(self.db_path)
        try:
            self.assertEqual(other.used("test-provider", utc_day="2026-11-21"), 2)
        finally:
            other.close()

    def test_missing_quota_limit_fails_closed(self):
        result = self.ledger.reserve("test-provider", 1, 0, utc_day="2026-11-21")
        self.assertFalse(result["reserved"])
        self.assertEqual(result["reason"], "daily_quota_limit_not_configured")


class ACCloudAdapterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp.name, "adapter.sqlite3")
        self.catalog = ProviderCatalog()

    def tearDown(self):
        self.temp.cleanup()

    def test_default_adapter_never_selects_unverified_provider(self):
        adapter = ACCloudAdapter(self.db_path, self.catalog)
        try:
            plan = adapter.plan("gpu_experiment")
            self.assertEqual(plan["status"], "unavailable")
            self.assertEqual(plan["paid_fallback"], "prohibited")
            self.assertFalse(plan["provider_network_calls"])
        finally:
            adapter.ledger.close()

    def test_verified_provider_is_planned_then_quota_reserved_without_dispatch(self):
        evidence = {
            "current_free_terms_verified": True,
            "no_card_requirement_verified": True,
            "billing_disabled_verified": True,
            "quota_guard_verified": True,
            "region_supported_verified": True,
        }
        adapter = ACCloudAdapter(
            self.db_path, self.catalog,
            approved_evidence={"kaggle": evidence},
            daily_quota_limits={"kaggle": 3},
        )
        try:
            plan = adapter.plan("gpu_experiment", units=2)
            self.assertEqual(plan["status"], "eligible_not_connected")
            self.assertFalse(plan["reservation_created"])
            reserved = adapter.reserve("gpu_experiment", units=2)
            self.assertTrue(reserved["reservation_created"])
            self.assertEqual(reserved["status"], "reserved_locally_not_dispatched")
            blocked = adapter.reserve("gpu_experiment", units=2)
            self.assertFalse(blocked["reservation_created"])
            self.assertEqual(blocked["plan"]["status"], "unavailable")
            self.assertTrue(any(item["reason"] == "free_quota_exhausted"
                                for item in blocked["plan"]["blocked_candidates"]))
        finally:
            adapter.ledger.close()

    def test_unknown_task_and_invalid_units_are_rejected(self):
        adapter = ACCloudAdapter(self.db_path, self.catalog)
        try:
            with self.assertRaises(ValueError):
                adapter.plan("unlisted-task")
            with self.assertRaises(ValueError):
                adapter.plan("gpu_experiment", units=0)
        finally:
            adapter.ledger.close()


if __name__ == "__main__":
    unittest.main()
