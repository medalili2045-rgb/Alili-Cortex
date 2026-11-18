
import os
import json
import hmac
import time
import signal
import threading
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HOST = "127.0.0.1"
INTERNAL_PORT = 8080
PORT = int(os.environ.get("PORT", "10000"))
SHARED_KEY = os.environ.get("SEARXNG_GATEWAY_KEY", "").strip()

if len(SHARED_KEY) < 32:
    raise SystemExit("SEARXNG_GATEWAY_KEY must contain at least 32 characters")

os.environ["GRANIAN_HOST"] = HOST
os.environ["GRANIAN_PORT"] = str(INTERNAL_PORT)
os.environ.pop("SEARXNG_PORT", None)

SEARXNG_COMMAND = [
    "/usr/local/searxng/.venv/bin/granian",
    "searx.webapp:app",
]

child = subprocess.Popen(SEARXNG_COMMAND)
stop_event = threading.Event()


def internal_ready():
    if child.poll() is not None:
        return False

    try:
        with urlopen(
            f"http://{HOST}:{INTERNAL_PORT}/",
            timeout=3
        ) as response:
            return 200 <= response.status < 400
    except Exception:
        return False


class Gateway(BaseHTTPRequestHandler):

    server_version = "AliliGateway"
    sys_version = ""

    def send_json(self, status, payload):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/healthz":
            if internal_ready():
                self.send_json(200, {"ok": True})
            else:
                self.send_json(503, {"ok": False})
            return

        if parsed.path != "/search":
            self.send_json(404, {"error": "Not found"})
            return

        supplied_key = self.headers.get(
            "X-Alili-Search-Key", ""
        )

        if not hmac.compare_digest(supplied_key, SHARED_KEY):
            self.send_json(401, {"error": "Unauthorized"})
            return

        if not internal_ready():
            self.send_json(503, {"error": "Search engine unavailable"})
            return

        params = parse_qs(parsed.query)
        query = params.get("q", [""])[0].strip()

        if not query or len(query) > 500:
            self.send_json(400, {"error": "Invalid query"})
            return

        upstream_query = urlencode({
            "q": query,
            "format": "json",
        })

        upstream_url = (
            f"http://{HOST}:{INTERNAL_PORT}/search?"
            f"{upstream_query}"
        )

        try:
            request = Request(
                upstream_url,
                headers={"Accept": "application/json"},
                method="GET",
            )

            with urlopen(request, timeout=25) as response:
                data = response.read(2_000_000)

            parsed_data = json.loads(data.decode("utf-8"))

            results = parsed_data.get("results", [])
            if not isinstance(results, list):
                results = []

            safe_results = []

            for item in results[:10]:
                if not isinstance(item, dict):
                    continue

                safe_results.append({
                    "title": str(item.get("title", ""))[:300],
                    "url": str(item.get("url", ""))[:2000],
                    "content": str(item.get("content", ""))[:1200],
                    "engine": str(item.get("engine", ""))[:80],
                })

            self.send_json(200, {
                "ok": True,
                "query": query,
                "results": safe_results,
            })

        except HTTPError as error:
            self.send_json(502, {"error": "Search upstream error"})
        except (URLError, TimeoutError, ValueError, OSError):
            self.send_json(502, {"error": "Search request failed"})

    def do_POST(self):
        self.send_json(405, {"error": "Method not allowed"})

    def log_message(self, format, *args):
        print("Gateway:", format % args)


server = ThreadingHTTPServer(("0.0.0.0", PORT), Gateway)
server.daemon_threads = True


def shutdown(signum, frame):
    stop_event.set()
    threading.Thread(target=server.shutdown, daemon=True).start()


signal.signal(signal.SIGTERM, shutdown)
signal.signal(signal.SIGINT, shutdown)

print(f"Alili Cortex Gateway listening on port {PORT}", flush=True)

try:
    server.serve_forever(poll_interval=0.5)
finally:
    server.server_close()

    if child.poll() is None:
        child.terminate()
        try:
            child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
