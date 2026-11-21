import unittest

from alili_engine.execution_sandbox import ACExecutionSandbox, ExecutionRejected


class ACExecutionSandboxTests(unittest.TestCase):
    def setUp(self):
        self.runner = ACExecutionSandbox(timeout_seconds=0.5)

    def test_runs_basic_python_without_imports(self):
        result = self.runner.run("total = sum(range(5))\nprint(total)")
        self.assertTrue(result["ok"])
        self.assertEqual(result["stdout"], "10\n")
        self.assertEqual(result["status"], "completed")

    def test_rejects_imports_and_attribute_access(self):
        for code in ("import os", "print((1).__class__)"):
            with self.subTest(code=code):
                with self.assertRaises(ExecutionRejected):
                    self.runner.run(code)

    def test_rejects_unapproved_names_and_calls(self):
        with self.assertRaises(ExecutionRejected):
            self.runner.run("open('secret.txt')")
        with self.assertRaises(ExecutionRejected):
            self.runner.run("unknown_function()")

    def test_enforces_code_and_input_limits(self):
        with self.assertRaises(ExecutionRejected):
            self.runner.run("x = 1\n" * 5000)
        with self.assertRaises(ExecutionRejected):
            self.runner.run("print(1)", input_text="x" * 9000)

    def test_timeout_stops_long_running_loop(self):
        result = self.runner.run("while True:\n    pass")
        self.assertEqual(result["status"], "timeout")

    def test_status_discloses_non_hardened_boundary(self):
        status = self.runner.status()
        self.assertEqual(status["isolation"], "best_effort_not_a_hardened_os_boundary")
        self.assertEqual(status["paid_fallback"], "prohibited")


if __name__ == "__main__":
    unittest.main()
