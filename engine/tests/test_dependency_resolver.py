import json
import unittest
from pathlib import Path

from alili_engine.dependency_resolver import (
    DependencyResolutionError, DependencyResolver, parse_requirement,
    version_satisfies, _request_json
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
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.requests = []

    def __call__(self, request, timeout=0):
        self.requests.append((request, timeout))
        return FakeResponse(self.payloads.pop(0))


def pypi(name, version, deps=(), license_id="MIT"):
    return {"info": {"name": name, "version": version,
                     "requires_dist": list(deps),
                     "license_expression": license_id,
                     "license": license_id, "classifiers": []},
            "urls": [{"filename": name + ".whl",
                      "url": "https://files.pythonhosted.org/example.whl",
                      "digests": {"sha256": "b" * 64}, "yanked": False}]}


class DependencyResolverTests(unittest.TestCase):
    def setUp(self):
        path = Path(__file__).parents[1] / "data" / "library_candidates.json"
        self.manifest = json.loads(path.read_text(encoding="utf-8"))
        self.manifest["candidates"] = [
            {"library_id": "root-a", "package_name": "root-a"},
        ]

    def test_requirement_parser_preserves_extras_and_markers(self):
        req = parse_requirement('sample[fast]>=1.2,<2; python_version >= "3.10"')
        self.assertEqual(req["name"], "sample")
        self.assertEqual(req["specifier"], ">=1.2,<2")
        self.assertIn("python_version", req["marker"])

    def test_supported_version_constraints(self):
        self.assertTrue(version_satisfies("2.4.0", ">=2,<3"))
        self.assertFalse(version_satisfies("3.0.0", ">=2,<3"))
        self.assertTrue(version_satisfies("1.8.4", "~=1.8"))
        self.assertTrue(version_satisfies("1.2.5", "==1.2.*"))
        self.assertIsNone(version_satisfies("1!2.0", ">=1"))

    def test_resolves_transitive_graph_and_keeps_quarantine(self):
        fake = FakeOpener([
            pypi("root-a", "1.0.0", ["dep-b>=2,<3"]),
            pypi("dep-b", "2.2.0", ["dep-c==4.1.*"]),
            pypi("dep-c", "4.1.7"),
        ])
        report = DependencyResolver(self.manifest, opener=fake).resolve(check_osv=False)
        self.assertEqual(report["summary"]["unique_nodes"], 3)
        self.assertEqual(report["summary"]["dependency_edges"], 2)
        self.assertTrue(report["summary"]["fully_resolved"])
        self.assertTrue(all(n["admission_status"] == "quarantined" for n in report["nodes"]))
        self.assertTrue(all(n["install_enabled"] is False for n in report["nodes"]))
        self.assertEqual(len(fake.requests), 3)

    def test_conflicting_constraints_fail_closed(self):
        manifest = {"candidates": [
            {"library_id": "root-a", "package_name": "root-a"},
            {"library_id": "root-b", "package_name": "root-b"},
        ]}
        fake = FakeOpener([
            pypi("root-a", "1.0.0", ["shared>=2"]),
            pypi("root-b", "1.0.0", ["shared<2"]),
            pypi("shared", "2.1.0"),
        ])
        report = DependencyResolver(manifest, opener=fake).resolve(check_osv=False)
        shared = next(n for n in report["nodes"] if n["name"] == "shared")
        self.assertEqual(shared["resolution_status"], "constraint_conflict")
        self.assertFalse(report["summary"]["fully_resolved"])

    def test_unapproved_host_rejected(self):
        with self.assertRaisesRegex(DependencyResolutionError, "endpoint_not_allowlisted"):
            _request_json("https://example.org/pypi/pkg/json", opener=FakeOpener([]))


if __name__ == "__main__":
    unittest.main()
