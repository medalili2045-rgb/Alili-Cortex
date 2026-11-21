import json
import unittest
from pathlib import Path

from alili_engine.library_inspector import (
    InspectionError, LibraryInspector, _extract_dependencies, _safe_json_request
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, limit=-1):
        return self.payload[:limit]


class FakeOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout=0):
        self.requests.append((request, timeout))
        return FakeResponse(self.responses.pop(0))


class LibraryInspectorTests(unittest.TestCase):
    def setUp(self):
        manifest_path = Path(__file__).parents[1] / "data" / "library_candidates.json"
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def test_rejects_packages_outside_curated_allowlist(self):
        inspector = LibraryInspector(self.manifest, opener=FakeOpener([]))
        with self.assertRaisesRegex(InspectionError, "not_in_ac_allowlist"):
            inspector.inspect("some-random-package")

    def test_rejects_non_https_or_unapproved_hosts(self):
        with self.assertRaisesRegex(InspectionError, "endpoint_not_allowlisted"):
            _safe_json_request("https://example.com/package/json",
                               opener=FakeOpener([]))

    def test_extracts_dependency_names_without_installing(self):
        result = _extract_dependencies([
            "starlette>=0.30; python_version > '3.9'",
            "pydantic>=2",
            "starlette>=0.30; python_version > '3.9'",
            "!!! not a valid requirement",
        ])
        self.assertEqual(len(result), 2)
        self.assertEqual({item["name"] for item in result},
                         {"starlette", "pydantic"})

    def test_inspection_is_metadata_only_and_keeps_quarantine(self):
        package = next(x for x in self.manifest["candidates"]
                       if x["package_name"] == "fastapi")
        fake = FakeOpener([{
            "info": {
                "name": "fastapi", "version": "9.8.7",
                "license_expression": "MIT",
                "license": "MIT",
                "classifiers": ["License :: OSI Approved :: MIT License"],
                "requires_dist": ["starlette>=0.30", "pydantic>=2"],
                "summary": "test package", "requires_python": ">=3.9",
            },
            "urls": [{
                "filename": "fastapi-9.8.7-py3-none-any.whl",
                "packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/test.whl",
                "digests": {"sha256": "a" * 64}, "size": 123, "yanked": False,
            }],
        }, {"vulns": []}])
        result = LibraryInspector(self.manifest, opener=fake).inspect("fastapi")
        self.assertEqual(result["resolved_version"], "9.8.7")
        self.assertEqual(result["artifact"]["sha256"], "a" * 64)
        self.assertFalse(result["artifact"]["downloaded"])
        self.assertEqual(result["security"]["vulnerability_count"], 0)
        self.assertEqual(result["admission_status"], "quarantined")
        self.assertFalse(result["install_enabled"])
        self.assertFalse(result["license"]["approved"])
        self.assertEqual(len(fake.requests), 2)

    def test_osv_failure_does_not_approve_or_fail_open(self):
        fake = FakeOpener([{
            "info": {"name": "fastapi", "version": "1.2.3",
                     "requires_dist": []}, "urls": []
        }])
        result = LibraryInspector(self.manifest, opener=fake).inspect("fastapi")
        self.assertEqual(result["security"]["status"], "unavailable")
        self.assertEqual(result["admission_status"], "quarantined")
        self.assertEqual(result["license"]["status"], "license_evidence_missing")


if __name__ == "__main__":
    unittest.main()
