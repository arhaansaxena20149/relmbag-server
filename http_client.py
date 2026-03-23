from __future__ import annotations

import http.client
import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse


@dataclass
class SimpleResponse:
    ok: bool
    status_code: int
    text: str

    def json(self) -> Any:
        if not self.text:
            return None
        return json.loads(self.text)


def _http_request(method: str, url: str, json_payload: Any | None = None, timeout: int = 10) -> SimpleResponse:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return SimpleResponse(ok=False, status_code=0, text="Only https URLs are supported by fallback transport.")

    body: bytes | None = None
    headers: dict[str, str] = {}
    if json_payload is not None:
        body = json.dumps(json_payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    # Fallback transport only: disable TLS verification to avoid missing CA bundles.
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    conn = http.client.HTTPSConnection(
        host=parsed.hostname,
        port=parsed.port or 443,
        timeout=timeout,
        context=context,
    )

    try:
        path = parsed.path or "/"
        if parsed.query:
            path = f"{path}?{parsed.query}"
        conn.request(method=method, url=path, body=body, headers=headers)
        resp = conn.getresponse()
        status_code = int(getattr(resp, "status", 0) or 0)
        text = resp.read().decode("utf-8", errors="replace")
        return SimpleResponse(ok=200 <= status_code < 300, status_code=status_code, text=text)
    except Exception as e:
        return SimpleResponse(ok=False, status_code=0, text=str(e))
    finally:
        try:
            conn.close()
        except Exception:
            pass


def get(url: str, timeout: int = 10) -> SimpleResponse:
    return _http_request("GET", url, json_payload=None, timeout=timeout)


def post(url: str, json: Any | None = None, timeout: int = 10) -> SimpleResponse:
    return _http_request("POST", url, json_payload=json, timeout=timeout)

