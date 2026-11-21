import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from alili_engine.api import create_handler
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class AICapabilityObservatoryAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = EngineService(TaskStore(self.temp.name + "/engine.sqlite3"))
        self.token = "ac-observatory-api-test-token-longer-than-32-chars"
        self.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), create_handler(self.service, self.token))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp.cleanup()

    def request_json(self, path, body=None, authorized=True):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if authorized:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(self.base + path, data=data, headers=headers,
                          method="POST" if body is not None else "GET")
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_capability_catalog_and_response_policy_are_authenticated(self):
        status, payload = self.request_json("/v1/ai-observatory/capabilities?q=Copilot")
        self.assertEqual(status, 200)
        self.assertEqual(payload["capabilities"][0]["id"], "github_copilot")
        status, payload = self.request_json("/v1/ai-observatory/response-style")
        self.assertEqual(status, 200)
        self.assertEqual(payload["policy"]["id"], "ac_clear_response_v1")
        status, payload = self.request_json("/v1/ai-observatory/capabilities", authorized=False)
        self.assertEqual(status, 401)

    def test_study_post_is_persisted_in_quarantine(self):
        status, payload = self.request_json("/v1/ai-observatory/studies", {
            "capability_id": "github_copilot",
            "title": "Copilot repository context",
            "notes": "Study repository instructions, code review and agent delegation.",
            "source_url": "https://docs.github.com/en/copilot",
        })
        self.assertEqual(status, 202)
        self.assertEqual(payload["study"]["status"], "quarantined")
        status, listed = self.request_json(
            "/v1/ai-observatory/studies?capability_id=github_copilot")
        self.assertEqual(status, 200)
        self.assertEqual(len(listed["studies"]), 1)

    def test_response_evaluation_endpoint_is_structural_only(self):
        status, payload = self.request_json("/v1/ai-observatory/evaluate-response", {
            "text": "Yes, it is possible.\n\nWe can implement it in two steps."
        })
        self.assertEqual(status, 200)
        self.assertEqual(payload["evaluation"]["semantic_accuracy"], "not_evaluated")


if __name__ == "__main__":
    unittest.main()
