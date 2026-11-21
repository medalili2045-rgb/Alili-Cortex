import unittest

from alili_engine.license_intelligence import (
    LicenseIntelligence, analyze_license_expression, parse_spdx_expression,
)


class LicenseIntelligenceTests(unittest.TestCase):
    def test_permissive_identifiers_are_candidates_not_approvals(self):
        result = analyze_license_expression("MIT")
        self.assertEqual(result["classification"], "permissive_candidate")
        self.assertFalse(result["approved"])
        self.assertTrue(result["review_required"])

    def test_copyleft_is_flagged(self):
        for expression in ("GPL-3.0-only", "AGPL-3.0-only", "LGPL-2.1-only", "MPL-2.0"):
            with self.subTest(expression=expression):
                self.assertEqual(analyze_license_expression(expression)["classification"], "copyleft")

    def test_and_expression_keeps_all_obligations(self):
        result = analyze_license_expression("MIT AND GPL-3.0-only")
        self.assertEqual(result["classification"], "copyleft")
        self.assertEqual(result["operator"], "AND")
        self.assertEqual(set(result["identifiers"]), {"MIT", "GPL-3.0-only"})
        self.assertIn("combined_obligations", result["risk"])

    def test_or_expression_requires_a_choice(self):
        result = analyze_license_expression("MIT OR GPL-3.0-only")
        self.assertEqual(result["classification"], "copyleft")
        self.assertEqual(result["risk"], "choice_required_between_alternatives")
        self.assertFalse(result["approved"])

    def test_parentheses_and_exception_are_parsed(self):
        result = analyze_license_expression("(MIT OR Apache-2.0) AND GPL-2.0-only WITH Classpath-exception-2.0")
        self.assertEqual(result["operator"], "AND")
        self.assertEqual(result["classification"], "copyleft")
        self.assertIn("license_exception_requires_review", result["classifications"])

    def test_unknown_and_missing_fail_closed(self):
        self.assertEqual(analyze_license_expression("MadeUp-License-9.9")["classification"], "unknown")
        self.assertEqual(analyze_license_expression(None)["status"], "missing")
        self.assertEqual(analyze_license_expression("MIT ???")["status"], "unparsed")

    def test_non_spdx_classifier_does_not_approve(self):
        report = {"nodes": [{
            "name": "package-a", "version": "1.0", "root": True,
            "resolution_status": "resolved",
            "license": {"expression": None, "text": "MIT License", "classifiers": ["License :: OSI Approved :: MIT License"]},
        }]}
        result = LicenseIntelligence().analyze(report)
        self.assertEqual(result["packages"][0]["license"]["classification"], "unknown")
        self.assertEqual(result["packages"][0]["license"]["status"], "text_only_unparsed")
        self.assertEqual(result["summary"]["approval_count"], 0)

    def test_dependency_graph_audit_keeps_all_nodes_quarantined(self):
        report = {"nodes": [
            {"name": "a", "version": "1.0", "root": True, "resolution_status": "resolved",
             "license": {"expression": "MIT"}},
            {"name": "b", "version": "2.0", "root": False, "resolution_status": "resolved",
             "license": {"expression": "GPL-3.0-only"}},
        ]}
        result = LicenseIntelligence().analyze(report)
        self.assertEqual(result["summary"]["packages_audited"], 2)
        self.assertTrue(result["summary"]["all_packages_quarantined"])
        self.assertEqual(result["summary"]["approval_count"], 0)
        self.assertEqual(len(result["findings"]), 2)

    def test_invalid_report_shape_rejected(self):
        with self.assertRaises(ValueError):
            LicenseIntelligence().analyze({})


if __name__ == "__main__":
    unittest.main()
