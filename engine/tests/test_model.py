import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from alili_engine.api import create_handler
from alili_engine.model import LocalModelClient, LocalModelError
from alili_engine.service import EngineService
from alili_engine.store import TaskStore


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        body = json.dumps({"object": "list", "data": self.server.advertised_models}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        self.server.request_body = json.loads(self.rfile.read(length))
        body = json.dumps({
            "model": "tiny-local-test",
            "choices": [{"message": {"role": "assistant", "content": "مرحباً من النموذج المحلي"}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 4},
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class LocalModelTests(unittest.TestCase):
    def setUp(self):
        self.server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.server.request_body = None
        self.server.advertised_models = [{"id": "tiny-local-test", "object": "model"}]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.client = LocalModelClient(f"http://127.0.0.1:{self.server.server_port}/v1", "tiny-local-test", timeout=2)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_generates_using_local_openai_compatible_endpoint(self):
        result = self.client.generate([{"role": "user", "content": "قل مرحباً"}])
        self.assertEqual(result["source"], "local")
        self.assertEqual(result["content"], "مرحباً من النموذج المحلي")
        self.assertEqual(self.server.request_body["model"], "tiny-local-test")
        self.assertFalse(self.server.request_body["stream"])

    def test_refuses_non_loopback_or_https_endpoints(self):
        for endpoint in ("https://127.0.0.1:8080/v1", "http://8.8.8.8:8080/v1", "http://example.com:8080/v1"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                LocalModelClient(endpoint)

    def test_refuses_redirects_without_forwarding_prompt_to_destination(self):
        from http.server import BaseHTTPRequestHandler

        class CaptureHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.server.received = True
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_args):
                pass

        class RedirectHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.send_response(302)
                self.send_header("Location", self.server.redirect_to)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, *_args):
                pass

        destination = HTTPServer(("127.0.0.1", 0), CaptureHandler)
        destination.received = False
        destination_thread = threading.Thread(target=destination.serve_forever, daemon=True)
        destination_thread.start()
        redirect = HTTPServer(("127.0.0.1", 0), RedirectHandler)
        redirect.redirect_to = "http://127.0.0.1:%s/capture" % destination.server_port
        redirect_thread = threading.Thread(target=redirect.serve_forever, daemon=True)
        redirect_thread.start()
        try:
            client = LocalModelClient(
                "http://127.0.0.1:%s/v1" % redirect.server_port, "redirect-test", timeout=2)
            with self.assertRaisesRegex(LocalModelError, "redirects are disabled"):
                client.generate([{"role": "user", "content": "private prompt"}])
            self.assertFalse(destination.received)
        finally:
            redirect.shutdown()
            redirect.server_close()
            redirect_thread.join(timeout=2)
            destination.shutdown()
            destination.server_close()
            destination_thread.join(timeout=2)

    def test_rejects_invalid_messages(self):
        with self.assertRaises(ValueError):
            self.client.generate([{"role": "tool", "content": "not allowed"}])

    def test_status_probe_reports_ready_only_when_configured_model_is_advertised(self):
        status = self.client.status()
        self.assertEqual(status["status"], "ready")
        self.assertTrue(status["model_available"])
        self.assertNotIn("endpoint", status)

    def test_status_probe_reports_empty_or_missing_model_without_claiming_ready(self):
        self.server.advertised_models = []
        empty = self.client.status()
        self.assertEqual(empty["status"], "reachable_no_models")
        self.assertEqual(empty["reason"], "no_models_advertised")
        self.server.advertised_models = [{"id": "different-model"}]
        missing = self.client.status()
        self.assertEqual(missing["status"], "reachable_no_models")
        self.assertFalse(missing["model_available"])

    def test_status_probe_reports_unreachable_without_leaking_endpoint(self):
        self.server.shutdown()
        status = self.client.status()
        self.assertEqual(status["status"], "unreachable")
        self.assertNotIn("endpoint", status)
        self.assertNotIn(str(self.server.server_port), json.dumps(status))

    def test_never_uses_hosted_fallback(self):
        self.assertEqual(self.client.status()["fallback"], "disabled")


class EngineGenerateApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.model_server = HTTPServer(("127.0.0.1", 0), _Handler)
        self.model_server.request_body = None
        self.model_thread = threading.Thread(target=self.model_server.serve_forever, daemon=True)
        self.model_thread.start()
        client = LocalModelClient(f"http://127.0.0.1:{self.model_server.server_port}/v1", "tiny-local-test", timeout=2)
        service = EngineService(TaskStore(os.path.join(self.temp.name, "api.sqlite3")), model_client=client)
        self.token = "integration-test-token-at-least-32-chars"
        self.api_server = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(service, self.token))
        self.api_thread = threading.Thread(target=self.api_server.serve_forever, daemon=True)
        self.api_thread.start()
        self.base = f"http://127.0.0.1:{self.api_server.server_port}"

    def tearDown(self):
        self.api_server.shutdown()
        self.api_server.server_close()
        self.api_thread.join(timeout=2)
        self.model_server.shutdown()
        self.model_server.server_close()
        self.model_thread.join(timeout=2)
        self.temp.cleanup()

    def test_authenticated_generate_route_uses_only_local_model(self):
        request = Request(
            self.base + "/v1/generate",
            data=json.dumps({"messages": [{"role": "user", "content": "اختبار"}]}).encode(),
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["result"]["source"], "local")
        self.assertEqual(payload["result"]["content"], "مرحباً من النموذج المحلي")
        self.assertEqual(self.model_server.request_body["model"], "tiny-local-test")

    def test_model_status_reports_live_local_runtime_readiness(self):
        request = Request(self.base + "/v1/model/status", headers={"Authorization": "Bearer " + self.token})
        with urlopen(request) as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["model"]["status"], "ready")
        self.assertTrue(payload["model"]["model_available"])
        self.assertNotIn("endpoint", payload["model"])
        self.assertEqual(payload["model"]["fallback"], "disabled")


if __name__ == "__main__":
    unittest.main()
