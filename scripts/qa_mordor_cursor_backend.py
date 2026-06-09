#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_NAV_REPO = Path(os.environ.get("NAVSTRATEGIES_REPO", "~/repos/navstrategies")).expanduser()

try:
    import nbformat
    from nbformat.v4 import new_code_cell, new_notebook
    from playwright.sync_api import Page, sync_playwright
except ModuleNotFoundError:
    fallback_python = DEFAULT_NAV_REPO / ".venv" / "bin" / "python"
    if fallback_python.exists() and os.environ.get("MORDOR_CURSOR_QA_REEXEC") != "1":
        env = os.environ.copy()
        env["MORDOR_CURSOR_QA_REEXEC"] = "1"
        os.execve(str(fallback_python), [str(fallback_python), __file__, *sys.argv[1:]], env)
    raise


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def create_notebook(nav_repo: Path, name: str) -> Path:
    notebook_path = nav_repo / "notebooks" / "qa_scratch" / f"{name}.ipynb"
    nb = new_notebook(
        cells=[new_code_cell("# Mordor Cursor backend QA scratch notebook\n")],
        metadata={
            "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
    )
    notebook_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, notebook_path)
    return notebook_path


def saved_mordor_cells(notebook_path: Path) -> list[dict[str, Any]]:
    saved = nbformat.read(notebook_path, as_version=4)
    rows: list[dict[str, Any]] = []
    for cell in saved.cells:
        metadata = cell.get("metadata", {}).get("mordor")
        if not metadata:
            continue
        source = str(cell.get("source", ""))
        rows.append(
            {
                "cell_type": cell.cell_type,
                "role": metadata.get("role"),
                "first_line": source.splitlines()[0] if source.splitlines() else "",
                "source": source[:1000],
                "output_count": len(cell.get("outputs", []) or []),
            }
        )
    return rows


def open_notebook(page: Page, *, base_url: str, jupyter_prefix: str, nav_repo: Path, notebook_path: Path) -> None:
    notebook_rel = notebook_path.relative_to(nav_repo / "notebooks").as_posix()
    page.goto(f"{base_url.rstrip('/')}{jupyter_prefix}/lab/tree/{notebook_rel}?reset", wait_until="domcontentloaded", timeout=60_000)
    page.locator(".jp-Notebook:visible").first.wait_for(timeout=60_000)
    page.wait_for_function("() => !!window.mordorNotebookLab && !!window.mordorNotebookLab.openPanel", timeout=60_000)


def click_mordor_button(page: Page) -> None:
    button = page.locator("button[aria-label='Mordor']").first
    button.wait_for(state="visible", timeout=60_000)
    button.click(timeout=30_000)
    page.locator("[data-mordor-product-panel]").wait_for(timeout=120_000)


def configure_cursor_backend(page: Page) -> dict[str, Any]:
    selector = page.locator("[data-mordor-agent-select]")
    selector.wait_for(state="visible", timeout=30_000)
    selector.select_option("cursor")
    selected = selector.input_value()
    panel_text = page.locator("[data-mordor-product-panel]").inner_text(timeout=30_000)
    return {
        "selector_visible": True,
        "selected": selected,
        "panel_has_cursor": "Cursor" in panel_text,
        "panel_has_codex": "Codex" in panel_text,
    }


def send_prompt(page: Page, notebook_path: Path, prompt: str, expected: str, screenshot_path: Path) -> dict[str, Any]:
    page.locator("[data-mordor-prompt]").fill(prompt, timeout=30_000)
    page.locator("[data-mordor-send]").click(timeout=30_000)
    deadline = time.time() + 900
    panel_after = ""
    body_text = ""
    while time.time() < deadline:
        panel_after = page.locator("[data-mordor-product-panel]").inner_text(timeout=30_000)
        body_text = page.locator("body").inner_text(timeout=30_000)
        if "Status: Done" in panel_after and expected in body_text:
            break
        if "Status: Failed" in panel_after or "Status: Cancelled" in panel_after:
            break
        time.sleep(1.0)
    page.screenshot(path=str(screenshot_path), full_page=True)
    return {
        "status_done": "Status: Done" in panel_after,
        "expected_visible": expected in body_text,
        "panel_after": panel_after,
        "mordor_cells": saved_mordor_cells(notebook_path),
        "screenshot": str(screenshot_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Browser QA for Mordor Cursor Agent backend.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5011")
    parser.add_argument("--jupyter-prefix", default="/jlab")
    parser.add_argument("--nav-repo", type=Path, default=DEFAULT_NAV_REPO)
    parser.add_argument("--artifact-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    nav_repo = args.nav_repo.expanduser().resolve()
    stamp = utc_stamp()
    artifact_dir = (args.artifact_dir or nav_repo / "milestones" / "mordor_cursor_backend_qa" / stamp).expanduser().resolve()
    screenshots_dir = artifact_dir / "screenshots"
    notebooks_dir = artifact_dir / "notebooks"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    notebooks_dir.mkdir(parents=True, exist_ok=True)

    notebook_path = create_notebook(nav_repo, f"mordor_cursor_backend_{stamp}")
    first_prompt = (
        "Create exactly one markdown notebook cell through Mordor. Its first line must be "
        "'## Mordor generated: cursor fallback one'. The body must say 'cursor fallback one inserted live.' "
        "Do not create code cells and do not edit notebook files directly."
    )
    second_prompt = (
        "Create exactly one markdown notebook cell through Mordor. Its first line must be "
        "'## Mordor generated: cursor fallback two'. The body must say 'cursor fallback two inserted live.' "
        "Do not create code cells and do not edit notebook files directly."
    )
    result: dict[str, Any] = {
        "ok": False,
        "artifact_dir": str(artifact_dir),
        "notebook": str(notebook_path),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        context.add_init_script(
            """
            window.localStorage.setItem('mordorCursorCommand', 'cursor-agent');
            window.localStorage.setItem('mordorCursorSandbox', 'disabled');
            window.localStorage.setItem('mordorCursorForce', 'true');
            window.localStorage.setItem('mordorAgentBackend', 'cursor');
            """
        )
        page = context.new_page()
        try:
            open_notebook(
                page,
                base_url=args.base_url,
                jupyter_prefix="/" + args.jupyter_prefix.strip("/"),
                nav_repo=nav_repo,
                notebook_path=notebook_path,
            )
            click_mordor_button(page)
            selector = configure_cursor_backend(page)
            first = send_prompt(page, notebook_path, first_prompt, "cursor fallback one inserted live.", screenshots_dir / "cursor_one.png")
            second = send_prompt(page, notebook_path, second_prompt, "cursor fallback two inserted live.", screenshots_dir / "cursor_two.png")
            cells = saved_mordor_cells(notebook_path)
            result.update({"selector": selector, "first": first, "second": second, "final_cells": cells})
            result["ok"] = bool(
                selector.get("selected") == "cursor"
                and first.get("status_done")
                and first.get("expected_visible")
                and second.get("status_done")
                and second.get("expected_visible")
                and any("cursor fallback one" in cell.get("source", "") for cell in cells)
                and any("cursor fallback two" in cell.get("source", "") for cell in cells)
            )
        finally:
            browser.close()

    shutil.copy2(notebook_path, notebooks_dir / notebook_path.name)
    write_json(artifact_dir / "summary.json", result)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
