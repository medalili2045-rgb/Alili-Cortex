"""Local-only OpenAI-compatible chat adapter (for llama.cpp server and compatible runtimes)."""

import ipaddress
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ModelNotConfigured(RuntimeError):
    pass


class LocalModelError(RuntimeError):
    pass


def _is_loopback(hostname: str) -> bool:
    if hostname.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(hostname).is_loopback
    except ValueError:
        return False


class _NoRedirectHandler(HTTPRedirectHandler):
    """Never forward prompts or responses to a redirect destination."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class LocalModelClient:
    """Talk only to a loopback model server; never follows redirects or uses hosted providers."""

    def __init__(self, base_url: str, model_name: str = "local-model", timeout: float = 90.0):
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or not _is_loopback(parsed.hostname or ""):
            raise ValueError("The model endpoint must be an HTTP loopback address.")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Credentials, query strings, and fragments are not allowed in the model URL.")
        if not parsed.port:
            raise ValueError("The model endpoint must include an explicit port.")
        if not 0 < timeout <= 300:
            raise ValueError("Model timeout must be between 0 and 300 seconds.")
        self.base_url = base_url.rstrip("/")
        self.model_name = model_name
        self.timeout = timeout

    def status(self) -> dict:
        """Probe only the explicitly configured loopback server's OpenAI /models endpoint."""
        result = {"configured": True, "kind": "local_loopback", "model": self.model_name,
                  "fallback": "disabled", "probe": "GET /models"}
        request = Request(self.base_url + "/models",
                          headers={"Accept": "application/json"}, method="GET")
        try:
            with build_opener(_NoRedirectHandler()).open(request, timeout=min(self.timeout, 3.0)) as response:
                raw = response.read(512_001)
                if len(raw) > 512_000:
                    return {**result, "status": "reachable_no_models",
                            "reason": "models_response_too_large", "model_count": 0}
                payload = json.loads(raw.decode("utf-8"))
        except HTTPError as exc:
            return {**result, "status": "unreachable",
                    "reason": "models_endpoint_http_error", "http_status": exc.code}
        except (URLError, TimeoutError, OSError):
            return {**result, "status": "unreachable", "reason": "runtime_unreachable"}
        except (UnicodeDecodeError, json.JSONDecodeError):
            return {**result, "status": "reachable_no_models",
                    "reason": "invalid_models_response", "model_count": 0}

        entries = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(entries, list):
            return {**result, "status": "reachable_no_models",
                    "reason": "invalid_models_response", "model_count": 0}
        model_ids = [item.get("id") for item in entries
                     if isinstance(item, dict) and isinstance(item.get("id"), str)]
        if not model_ids:
            return {**result, "status": "reachable_no_models",
                    "reason": "no_models_advertised", "model_count": 0}
        if self.model_name not in model_ids:
            return {**result, "status": "reachable_no_models",
                    "reason": "configured_model_not_advertised",
                    "model_count": len(model_ids), "model_available": False}
        return {**result, "status": "ready", "reason": "configured_model_available",
                "model_count": len(model_ids), "model_available": True}

    def generate(self, messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 512) -> dict:
        if not isinstance(messages, list) or not messages or len(messages) > 40:
            raise ValueError("messages must contain between 1 and 40 entries")
        safe_messages = []
        for item in messages:
            if not isinstance(item, dict) or item.get("role") not in {"system", "user", "assistant"}:
                raise ValueError("Each message must have a supported role and text content")
            content = item.get("content")
            if not isinstance(content, str) or not content.strip() or len(content) > 16000:
                raise ValueError("Message content must be non-empty text up to 16000 characters")
            safe_messages.append({"role": item["role"], "content": content})
        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if not 1 <= max_tokens <= 4096:
            raise ValueError("max_tokens must be between 1 and 4096")

        payload = json.dumps({"model": self.model_name, "messages": safe_messages,
                              "temperature": temperature, "max_tokens": max_tokens,
                              "stream": False}).encode("utf-8")
        request = Request(self.base_url + "/chat/completions", data=payload,
                          headers={"Content-Type": "application/json", "Accept": "application/json"},
                          method="POST")
        try:
            with build_opener(_NoRedirectHandler()).open(request, timeout=self.timeout) as response:
                raw_response = response.read(2_000_001)
                if len(raw_response) > 2_000_000:
                    raise LocalModelError("Local model response exceeded the 2 MB limit")
                result = json.loads(raw_response.decode("utf-8"))
        except HTTPError as exc:
            raise LocalModelError(f"Local model returned HTTP {exc.code}; redirects are disabled") from None
        except (URLError, TimeoutError, OSError):
            raise LocalModelError("Local model runtime is unreachable") from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise LocalModelError("Local model returned invalid JSON") from None

        try:
            content = result["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LocalModelError("Local model response did not match the chat-completions format") from None
        if not isinstance(content, str):
            raise LocalModelError("Local model returned non-text content")
        return {"model": result.get("model", self.model_name), "content": content,
                "usage": result.get("usage"), "source": "local"}
