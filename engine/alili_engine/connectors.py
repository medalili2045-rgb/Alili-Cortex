"""Safe, catalog-bound HTTPS documentation connector (text-only v1).

Only the exact HTTPS host recorded in the ecosystem catalog is reachable.
Requests are pinned to a prevalidated public IP, redirects are bounded and
revalidated, and fetched content is returned for quarantined study intake.
"""
import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit


MAX_DOCUMENT_BYTES = 1_000_000
REQUEST_TIMEOUT_SECONDS = 8
MAX_REDIRECTS = 3
_ALLOWED_TYPES = {"text/html", "application/xhtml+xml", "text/plain",
                  "text/markdown", "text/x-markdown", "application/json"}
_REDIRECTS = {301, 302, 303, 307, 308}


class ConnectorError(ValueError):
    """A source fetch was rejected or failed safely."""


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in {"script", "style", "noscript", "svg"}:
            self.skip_depth += 1
        elif tag.lower() in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in {"script", "style", "noscript", "svg"} and self.skip_depth:
            self.skip_depth -= 1
        elif tag.lower() in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth and data.strip():
            self.parts.append(data.strip())

    def text(self):
        return re.sub(r"\n[ \t]*\n+", "\n\n", "\n".join(self.parts)).strip()


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, hostname, address, port, timeout):
        super().__init__(hostname, port=port, timeout=timeout,
                         context=ssl.create_default_context())
        self._pinned_address = address

    def connect(self):
        raw = socket.create_connection((self._pinned_address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw, server_hostname=self.host)


class UniversalSourceConnector:
    """Fetch a bounded text document from a catalog source's exact official host."""

    def __init__(self, ecosystem_registry, *, resolver=None):
        self.ecosystem = ecosystem_registry
        self._resolver = resolver or socket.getaddrinfo

    def _target(self, source_id, url):
        source = self.ecosystem.get(source_id)
        if source is None:
            raise ConnectorError("unknown_ecosystem_source")
        canonical = urlsplit(source["url"])
        target = urlsplit(url)
        try:
            target_port = target.port
        except ValueError as exc:
            raise ConnectorError("invalid_source_url_port") from exc
        if (canonical.scheme != "https" or not canonical.hostname or
                target.scheme != "https" or target.username or target.password or
                target.hostname != canonical.hostname or target_port not in (None, 443) or
                target.fragment):
            raise ConnectorError("url_must_match_catalogued_https_host")
        try:
            records = self._resolver(target.hostname, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ConnectorError("source_dns_resolution_failed") from exc
        addresses = []
        for record in records:
            address = record[4][0]
            try:
                parsed = ipaddress.ip_address(address)
            except ValueError as exc:
                raise ConnectorError("source_dns_returned_invalid_address") from exc
            if not parsed.is_global:
                raise ConnectorError("source_resolves_to_non_public_address")
            addresses.append(address)
        if not addresses:
            raise ConnectorError("source_dns_returned_no_addresses")
        return target, addresses[0]

    @staticmethod
    def _normalize(body, content_type):
        charset_match = re.search(r"charset=([A-Za-z0-9._-]+)", content_type, re.I)
        charset = charset_match.group(1) if charset_match else "utf-8"
        try:
            raw = body.decode(charset, errors="replace")
        except LookupError:
            raw = body.decode("utf-8", errors="replace")
        if content_type.split(";", 1)[0].strip().lower() in {"text/html", "application/xhtml+xml"}:
            parser = _TextExtractor()
            parser.feed(raw)
            return parser.text()
        return raw.strip()

    def _request(self, target, address, if_none_match=None, if_modified_since=None):
        path = target.path or "/"
        if target.query:
            path += "?" + target.query
        connection = _PinnedHTTPSConnection(target.hostname, address, 443,
                                             REQUEST_TIMEOUT_SECONDS)
        try:
            connection.request("GET", path, headers={
                "Host": target.hostname,
                "User-Agent": "AliliCortex-SourceConnector/1.0 (+https://github.com/medalili2045-rgb/Alili-Cortex-Next)",
                "Accept": "text/html,application/xhtml+xml,text/markdown,text/plain,application/json",
                "Accept-Encoding": "identity",
                "Connection": "close",
                **({"If-None-Match": if_none_match} if if_none_match else {}),
                **({"If-Modified-Since": if_modified_since} if if_modified_since else {}),
            })
            response = connection.getresponse()
            headers = {key.lower(): value for key, value in response.getheaders()}
            if response.status in _REDIRECTS or response.status == 304:
                return response.status, headers, b""
            if response.status != 200:
                raise ConnectorError(f"source_http_status_{response.status}")
            content_type = headers.get("content-type", "").lower()
            media_type = content_type.split(";", 1)[0].strip()
            if media_type not in _ALLOWED_TYPES:
                raise ConnectorError("unsupported_source_content_type")
            declared = headers.get("content-length")
            if declared:
                try:
                    if int(declared) > MAX_DOCUMENT_BYTES:
                        raise ConnectorError("source_document_too_large")
                except ValueError as exc:
                    raise ConnectorError("invalid_source_content_length") from exc
            body = response.read(MAX_DOCUMENT_BYTES + 1)
            if len(body) > MAX_DOCUMENT_BYTES:
                raise ConnectorError("source_document_too_large")
            return response.status, headers, body
        except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
            raise ConnectorError("source_request_failed") from exc
        finally:
            connection.close()

    def fetch(self, source_id, artifact_url=None, *, if_none_match=None, if_modified_since=None):
        source = self.ecosystem.get(source_id)
        if source is None:
            raise ConnectorError("unknown_ecosystem_source")
        initial = artifact_url or source["url"]
        if not isinstance(initial, str) or len(initial) > 2048:
            raise ConnectorError("invalid_artifact_url")
        current = initial
        for redirect_count in range(MAX_REDIRECTS + 1):
            target, address = self._target(source_id, current)
            status, headers, body = self._request(target, address, if_none_match, if_modified_since)
            if status == 304:
                return {"source_id": source_id, "artifact_url": current, "not_modified": True,
                        "etag": headers.get("etag") or if_none_match,
                        "last_modified": headers.get("last-modified") or if_modified_since,
                        "retrieved_at": datetime.now(timezone.utc).isoformat()}
            if status in _REDIRECTS:
                location = headers.get("location")
                if not location or redirect_count >= MAX_REDIRECTS:
                    raise ConnectorError("source_redirect_limit_or_location_error")
                current = urljoin(current, location)
                continue
            content_type = headers["content-type"]
            content = self._normalize(body, content_type)
            if not content:
                raise ConnectorError("source_document_empty_after_text_extraction")
            return {
                "source_id": source_id, "title": headers.get("content-disposition", "").split("filename=")[-1].strip('"') or target.path.rsplit("/", 1)[-1] or source["name"],
                "artifact_url": current, "version": headers.get("etag") or headers.get("last-modified") or "unversioned",
                "etag": headers.get("etag"), "last_modified": headers.get("last-modified"),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "content_type": content_type, "content": content,
                "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "license_status": "review_required", "status": "quarantined",
                "redirect_count": redirect_count,
            }
        raise ConnectorError("source_redirect_limit_exceeded")
