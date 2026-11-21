import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from alili_engine.api import create_handler
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class LibraryFoundryApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        service = EngineService(TaskStore(self.temp.name + "/engine.sqlite3"))
        self.token = "ac-library-api-test-token-longer-than-32-chars"
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(service, self.token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"
        self.headers = {"Authorization": "Bearer " + self.token, "Content-Type": "application/json"}

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request_json(self, path, body=None, authenticated=True):
        headers = dict(self.headers) if authenticated else {"Content-Type": "application/json"}
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(self.base + path, data=data, headers=headers,
                          method="POST" if body is not None else "GET")
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as response:
            return response.code, json.loads(response.read())

    def register_body(self):
        return {
            "library_id": "sample-library",
            "name": "Sample Library",
            "version": "1.0.0",
            "ecosystem": "python",
            "source_url": "https://example.org/project",
            "license_id": "MIT",
            "domains": ["code"],
            "brains": ["code"],
        }

    def test_library_endpoints_require_authentication(self):
        status, payload = self.request_json("/v1/libraries", authenticated=False)
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "unauthorized")

    def test_register_quarantined_review_then_approve_and_filter(self):
        status, created = self.request_json("/v1/libraries", self.register_body())
        self.assertEqual(status, 202)
        self.assertEqual(created["library"]["status"], "quarantined")
        status, listed = self.request_json("/v1/libraries?status=quarantined&brain=code")
        self.assertEqual(status, 200)
        self.assertEqual(len(listed["libraries"]), 1)
        status, reviewed = self.request_json("/v1/libraries/sample-library/review", {
            "decision": "approve",
            "reviewer": "AC reviewer",
            "evidence_ref": "https://example.org/license",
            "artifact_scope": "package",
        })
        self.assertEqual(status, 200)
        self.assertEqual(reviewed["library"]["status"], "approved")
        status, detail = self.request_json("/v1/libraries/sample-library")
        self.assertEqual(status, 200)
        self.assertEqual(detail["library"]["license_status"], "approved")

    def test_unknown_license_cannot_be_approved_over_api(self):
        body = self.register_body()
        body["library_id"] = "unknown-license-lib"
        body["license_id"] = "UNKNOWN"
        self.assertEqual(self.request_json("/v1/libraries", body)[0], 202)
        status, payload = self.request_json("/v1/libraries/unknown-license-lib/review", {
            "decision": "approve", "reviewer": "reviewer",
            "evidence_ref": "https://example.org/license", "artifact_scope": "package",
        })
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"], "license_not_in_allowlist")

    def test_invalid_base64_is_rejected(self):
        body = self.register_body()
        body["library_id"] = "bad-base64-lib"
        body["artifact_base64"] = "not base64!"
        status, payload = self.request_json("/v1/libraries", body)
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_artifact_base64")


if __name__ == "__main__":
    unittest.main()
