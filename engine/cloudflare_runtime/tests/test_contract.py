"""Static safety/contract tests; do not require Cloudflare credentials or network."""
import pathlib
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class RuntimeContractTests(unittest.TestCase):
    def test_worker_is_separate_and_uses_python_workers(self):
        config = tomllib.loads((ROOT / "wrangler.toml").read_text())
        self.assertEqual(config["name"], "ac-cortex-python-runtime")
        self.assertEqual(config["main"], "src/entry.py")
        self.assertIn("python_workers", config["compatibility_flags"])
        self.assertEqual(config["d1_databases"][0]["binding"], "AC_DB")
        self.assertEqual(config["ai"]["binding"], "AI")

    def test_runtime_defaults_are_fail_closed(self):
        config = tomllib.loads((ROOT / "wrangler.toml").read_text())
        self.assertEqual(config["vars"]["AC_RUNTIME_INFERENCE_ENABLED"], "false")
        self.assertEqual(config["vars"]["AC_FREE_CLOUDFLARE_AI_CONFIRMED"], "false")

    def test_inference_never_calls_ai_binding(self):
        source = (ROOT / "src/entry.py").read_text()
        self.assertIn('"error": "inference_disabled"', source)
        self.assertNotIn("self.env.AI.run", source)
        self.assertNotIn("self.env.AI.run", source.replace(" ", ""))

    def test_no_local_process_or_thread_sandbox_imports(self):
        source = (ROOT / "src/entry.py").read_text()
        for forbidden in ("subprocess", "threading", "resource"):
            self.assertNotIn(forbidden, source)

    def test_migration_is_additive_and_non_destructive(self):
        sql = (ROOT / "migrations/0001_runtime_events.sql").read_text().upper()
        self.assertIn("CREATE TABLE IF NOT EXISTS", sql)
        self.assertNotIn("DROP TABLE", sql)
        self.assertNotIn("DELETE FROM", sql)


if __name__ == "__main__":
    unittest.main()
