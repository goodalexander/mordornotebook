#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from playwright.sync_api import sync_playwright


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Browser smoke for Mordor Notebook through the navstrategies gateway.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5011")
    parser.add_argument("--jupyter-prefix", default="/jlab")
    parser.add_argument("--chromium", default="/usr/bin/chromium-browser")
    parser.add_argument("--artifact", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    base_url = args.base_url.rstrip("/")
    prefix = "/" + args.jupyter_prefix.strip("/")
    request_urls: list[str] = []
    console_errors: list[str] = []
    result: dict[str, Any] = {
        "ok": False,
        "base_url": base_url,
        "jupyter_prefix": prefix,
        "request_urls": request_urls,
        "console_errors": console_errors,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=args.chromium,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page()
        page.on("request", lambda request: request_urls.append(request.url))
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.goto(f"{base_url}{prefix}/lab", wait_until="domcontentloaded", timeout=30_000)

        health = page.evaluate(
            """async (prefix) => {
                const response = await fetch(`${prefix}/mordor/api/health`, {credentials: 'same-origin'});
                return {status: response.status, ok: response.ok, payload: await response.json()};
            }""",
            prefix,
        )
        memory = page.evaluate(
            """async (prefix) => {
                const response = await fetch(`${prefix}/mordor/api/memory`, {credentials: 'same-origin'});
                return {status: response.status, ok: response.ok, payload: await response.json()};
            }""",
            prefix,
        )
        context = page.evaluate(
            """async (prefix) => {
                const response = await fetch(`${prefix}/mordor/api/notebook/context`, {credentials: 'same-origin'});
                return {status: response.status, ok: response.ok, payload: await response.json()};
            }""",
            prefix,
        )
        browser.close()

    raw_bridge_requests = []
    for url in request_urls:
        try:
            from urllib.parse import urlparse

            parsed = urlparse(url)
        except Exception:
            continue
        if (
            parsed.hostname == "127.0.0.1"
            and parsed.port not in {5011, 5012, 8890}
            and any(part in parsed.path for part in ("/context", "/memory", "/cell", "/agent", "/ops"))
        ):
            raw_bridge_requests.append(url)

    result.update(
        {
            "health": {"status": health.get("status"), "ok": health.get("ok")},
            "memory": {
                "status": memory.get("status"),
                "ok": memory.get("ok"),
                "names": [item.get("name") for item in (memory.get("payload", {}).get("objects") or [])],
            },
            "context": {"status": context.get("status"), "ok": context.get("ok")},
            "raw_bridge_requests": raw_bridge_requests,
            "failed_fetch_console_errors": [text for text in console_errors if "Failed to fetch" in text],
        }
    )
    result["ok"] = (
        health.get("status") == 200
        and memory.get("status") == 200
        and context.get("status") == 200
        and "browser_frame" in result["memory"]["names"]
        and not raw_bridge_requests
        and not result["failed_fetch_console_errors"]
    )

    if args.artifact:
        args.artifact.parent.mkdir(parents=True, exist_ok=True)
        args.artifact.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
