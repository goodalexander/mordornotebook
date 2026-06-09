"""Tiny JSON HTTP client for the kernel runtime bridge."""

from __future__ import annotations

import http.client
import json
from urllib.parse import urlparse
from typing import Any


class BridgeUnavailable(RuntimeError):
    pass


def request_json(base_url: str, method: str, path: str, payload: dict[str, Any] | None = None, timeout: float = 5.0) -> Any:
    parsed = urlparse(base_url)
    if parsed.scheme != "http":
        raise BridgeUnavailable(f"Unsupported bridge URL: {base_url}")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn = http.client.HTTPConnection(parsed.hostname or "127.0.0.1", parsed.port or 80, timeout=timeout)
    try:
        conn.request(method.upper(), path, body=body, headers=headers)
        response = conn.getresponse()
        text = response.read().decode("utf-8", errors="replace")
    except OSError as exc:
        raise BridgeUnavailable(str(exc)) from exc
    finally:
        conn.close()
    if response.status >= 400:
        raise BridgeUnavailable(f"{response.status} {response.reason}: {text}")
    return json.loads(text) if text else None
