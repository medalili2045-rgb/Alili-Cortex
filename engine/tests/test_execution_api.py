import json
import os
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

from alili_engine.api import create_handler
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class ExecutionApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        service = EngineService(TaskStore(os.path.join(self.temp.name, "execution-api.sqlite3")))
        self.token = "execution-test-token-long-enough-123"
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

    def test_execution_status_is_authenticated_and_discloses_limits(self):
        with self.assertRaises(HTTPError) as caught:
            urlopen(self.base + "/v1/execution/status")
        self.assertEqual(caught.exception.code, 401)
        with urlopen(Request(self.base + "/v1/execution/status", headers=self.headers)) as response:
            payload = json.loads(response.read())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["execution"]["paid_fallback"], "prohibited")

    def test_execution_endpoint_runs_restricted_python(self):
        request = Request(
            self.base + "/v1/execution/run",
            data=json.dumps({"code": "total = sum(range(5))\nprint(total)"}).encode(),
            headers=self.headers,
            method="POST",
        )
        with urlopen(request) as response:
            payload = json.loads(response.read())
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["execution"]["stdout"], "10\n")

    def test_execution_endpoint_rejects_imports(self):
        request = Request(
            self.base + "/v1/execution/run",
            data=json.dumps({"code": "import os"}).encode(),
            headers=self.headers,
            method="POST",
        )
        with self.assertRaises(HTTPError) as caught:
            urlopen(request)
        self.assertEqual(caught.exception.code, 400)


if __name__ == "__main__":
    unittest.main()
