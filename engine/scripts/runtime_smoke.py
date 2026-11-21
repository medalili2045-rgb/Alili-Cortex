"""Live HTTP smoke test for the AC engine process (standard library only)."""
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BASE = os.environ.get("AC_SMOKE_BASE_URL", "http://127.0.0.1:8765")
TOKEN = os.environ.get("ALILI_ENGINE_API_TOKEN", "")


def request(path, method="GET", payload=None, authenticated=True):
    headers = {"Accept": "application/json"}
    if authenticated:
        headers["Authorization"] = "Bearer " + TOKEN
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main():
    if len(TOKEN) < 32:
        raise SystemExit("Smoke test requires a test-only API token of at least 32 characters.")

    last_error = None
    for _ in range(30):
        try:
            status, health = request("/health", authenticated=False)
            if status == 200 and health.get("ok") is True:
                break
        except (URLError, TimeoutError, OSError) as exc:
            last_error = exc
        time.sleep(1)
    else:
        raise SystemExit(f"AC engine did not become healthy: {last_error}")

    status, _ = request("/v1/capabilities", authenticated=False)
    assert status == 401, "Private API routes must reject unauthenticated requests."

    checks = {
        "/v1/capabilities": "capabilities",
        "/v1/brains": "brains",
        "/v1/models": "models",
        "/v1/model/status": "model",
        "/v1/cloud/status": "cloud",
    }
    for path, key in checks.items():
        status, payload = request(path)
        assert status == 200 and payload.get("ok") is True and key in payload, path

    status, model = request("/v1/model/status")
    assert status == 200
    assert model["model"]["fallback"] == "disabled"

    status, created = request("/v1/tasks", "POST", {"input": "اشرح مفهوم الاستدلال"})
    assert status == 202 and created.get("ok") is True
    task = created["task"]
    assert task["status"] == "planned"
    assert task["capability_id"] == "task_planning"

    status, fetched = request("/v1/tasks/" + task["task_id"])
    assert status == 200 and fetched["task"]["task_id"] == task["task_id"]

    status, software = request("/v1/tasks", "POST", {"input": "أنشئ تطبيقاً"})
    assert status == 202
    assert software["task"]["plan"]["execution_status"] == "capability_not_implemented"

    print(json.dumps({
        "ok": True,
        "service": "alili-cortex-engine",
        "checks": [
            "live_http_health", "authentication_gate", "capability_registry",
            "brain_registry", "model_registry", "model_status",
            "cloud_fail_closed", "task_create_and_read", "execution_boundary_honest"
        ],
        "model_runtime": model["model"]["status"],
        "software_execution": software["task"]["plan"]["execution_status"],
        "note": "This validates the running API process, not model inference or sandbox execution."
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
