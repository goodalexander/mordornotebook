#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Any

import nbformat
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
from playwright.sync_api import sync_playwright


DEFAULT_NAV_REPO = Path(os.environ.get("NAVSTRATEGIES_REPO", "~/repos/navstrategies")).expanduser()


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def create_scratch_notebook(nav_repo: Path, stamp: str) -> Path:
    scratch_dir = nav_repo / "notebooks" / "qa_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    notebook_path = scratch_dir / f"mordor_live_panel_smoke_{stamp}.ipynb"
    code = f"""import pandas as pd
from mordornotebook import attach

panel = pd.DataFrame({{"ticker": ["AAPL", "NVDA", "MSFT"], "value": [1.0, 2.0, 3.0]}})
mordor = attach(
    repo={str(nav_repo)!r},
    goal="JupyterLab live Mordor panel QA",
    notebook_path={str(notebook_path)!r},
)
mordor.register("panel", panel)
mordor.panel()
"""
    nb = new_notebook(
        cells=[
            new_markdown_cell("# Mordor Live Panel Smoke"),
            new_code_cell(code),
        ],
        metadata={
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
    )
    nbformat.write(nb, notebook_path)
    return notebook_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Live JupyterLab browser QA for Mordor panel execution and cell insertion.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5011")
    parser.add_argument("--jupyter-prefix", default="/jlab")
    parser.add_argument("--nav-repo", type=Path, default=DEFAULT_NAV_REPO)
    parser.add_argument("--chromium", default="/usr/bin/chromium-browser")
    parser.add_argument("--artifact-dir", type=Path, default=None)
    return parser.parse_args()


def generated_audit_cell_count(notebook_path: Path) -> int:
    if not notebook_path.exists():
        return 0
    nb = nbformat.read(notebook_path, as_version=4)
    return sum(1 for cell in nb.cells if "Mordor Audit" in str(cell.get("source", "")))


def main() -> int:
    args = parse_args()
    nav_repo = args.nav_repo.expanduser().resolve()
    stamp = utc_stamp()
    artifact_dir = args.artifact_dir or nav_repo / "milestones" / "mordor_remote_qa" / stamp
    artifact_dir.mkdir(parents=True, exist_ok=True)
    notebook_path = create_scratch_notebook(nav_repo, stamp)
    notebook_rel = notebook_path.relative_to(nav_repo / "notebooks").as_posix()
    base_url = args.base_url.rstrip("/")
    prefix = "/" + args.jupyter_prefix.strip("/")
    result: dict[str, Any] = {
        "ok": False,
        "base_url": base_url,
        "jupyter_prefix": prefix,
        "notebook_path": str(notebook_path),
        "artifact_dir": str(artifact_dir),
        "console_errors": [],
        "raw_bridge_requests": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=args.chromium,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        request_urls: list[str] = []
        console_errors: list[str] = []
        page.on("request", lambda request: request_urls.append(request.url))
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        page.goto(f"{base_url}{prefix}/lab/tree/{notebook_rel}?reset", wait_until="domcontentloaded", timeout=60_000)
        notebook = page.locator(".jp-Notebook:visible").first
        notebook.wait_for(timeout=60_000)
        page.keyboard.press("Escape")
        before_cells = notebook.locator(".jp-Cell").count()
        bootstrap_error: str | None = None
        for _ in range(3):
            try:
                code_cell = notebook.locator(".jp-CodeCell").first
                code_cell.scroll_into_view_if_needed(timeout=10_000)
                code_cell.click(timeout=30_000)
                page.keyboard.press("Control+Enter")
                page.locator("[data-mordor-action='context']").wait_for(timeout=30_000)
                bootstrap_error = None
                break
            except Exception as exc:
                bootstrap_error = f"{type(exc).__name__}: {exc}"
                time.sleep(2.0)
        if bootstrap_error:
            raise RuntimeError(f"bootstrap cell did not render Mordor panel: {bootstrap_error}")
        page.locator("[data-mordor-action='context']").click(timeout=30_000)
        page.wait_for_function(
            """() => {
                const out = document.querySelector('[data-mordor-output]');
                return out && out.textContent.includes('memory');
            }""",
            timeout=30_000,
        )
        context_output = page.locator("[data-mordor-output]").inner_text(timeout=10_000)
        page.locator("[data-mordor-action='insert']").click(timeout=30_000)
        page.wait_for_function(
            """() => {
                const out = document.querySelector('[data-mordor-output]');
                return out && out.textContent.includes('persisted_notebook');
            }""",
            timeout=30_000,
        )
        insert_output = page.locator("[data-mordor-output]").inner_text(timeout=10_000)
        after_cells = notebook.locator(".jp-Cell").count()
        saved_insert_count = generated_audit_cell_count(notebook_path)
        reloaded_for_file_backed_insert = False
        after_reload_cells = after_cells
        if after_cells <= before_cells and saved_insert_count > 0:
            reloaded_for_file_backed_insert = True
            page.goto(f"{base_url}{prefix}/lab/tree/{notebook_rel}?reset", wait_until="domcontentloaded", timeout=60_000)
            notebook = page.locator(".jp-Notebook:visible").first
            notebook.wait_for(timeout=60_000)
            after_reload_cells = notebook.locator(".jp-Cell").count()
        screenshot_path = artifact_dir / "jupyterlab_live_panel.png"
        page.screenshot(path=str(screenshot_path), full_page=True)
        browser.close()

    for url in request_urls:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        if (
            parsed.hostname == "127.0.0.1"
            and parsed.port not in {5011, 5012, 8890}
            and any(part in parsed.path for part in ("/context", "/memory", "/cell", "/agent", "/ops"))
        ):
            result["raw_bridge_requests"].append(url)

    result.update(
        {
            "console_errors": console_errors,
            "before_cells": before_cells,
            "after_cells": after_cells,
            "after_reload_cells": after_reload_cells,
            "context_output_has_panel": "panel" in context_output,
            "insert_output": insert_output,
            "insert_applied_live": '"applied_live": true' in insert_output or "'applied_live': True" in insert_output,
            "insert_persisted_notebook": '"persisted_notebook": true' in insert_output or "'persisted_notebook': True" in insert_output,
            "saved_insert_count": saved_insert_count,
            "reloaded_for_file_backed_insert": reloaded_for_file_backed_insert,
            "screenshot": str(screenshot_path),
        }
    )
    result["ok"] = (
        result["context_output_has_panel"]
        and result["insert_persisted_notebook"]
        and result["saved_insert_count"] >= 1
        and after_reload_cells > before_cells
        and not result["raw_bridge_requests"]
        and not [text for text in console_errors if "Failed to fetch" in text]
    )
    summary_path = artifact_dir / "jupyterlab_live_panel.json"
    summary_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
