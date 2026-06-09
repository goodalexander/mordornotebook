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
    if fallback_python.exists() and os.environ.get("MORDOR_MENU_BUTTON_QA_REEXEC") != "1":
        env = os.environ.copy()
        env["MORDOR_MENU_BUTTON_QA_REEXEC"] = "1"
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
        cells=[new_code_cell("# Mordor menu-button QA scratch notebook\n")],
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
        rows.append(
            {
                "cell_type": cell.cell_type,
                "role": metadata.get("role"),
                "first_line": str(cell.get("source", "")).splitlines()[0] if str(cell.get("source", "")).splitlines() else "",
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


def send_prompt(page: Page, notebook_path: Path, screenshot_path: Path) -> dict[str, Any]:
    prompt = "can you identify how to load an equity parquet that is fresh for the equity universer"
    page.locator("[data-mordor-prompt]").fill(prompt, timeout=30_000)
    page.locator("[data-mordor-send]").click(timeout=30_000)
    deadline = time.time() + 180
    panel_after = ""
    body_text = ""
    while time.time() < deadline:
        panel_after = page.locator("[data-mordor-product-panel]").inner_text(timeout=30_000)
        body_text = page.locator("body").inner_text(timeout=30_000)
        if "Status: Done" in panel_after and "latest_trade_date" in body_text:
            break
        time.sleep(1.0)
    page.screenshot(path=str(screenshot_path), full_page=True)
    return {
        "status_done": "Status: Done" in panel_after,
        "latest_trade_date_visible": "latest_trade_date" in body_text,
        "panel_after": panel_after,
        "mordor_cells": saved_mordor_cells(notebook_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Browser QA for Mordor Notebook JupyterLab menu/toolbar access.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5011")
    parser.add_argument("--jupyter-prefix", default="/jlab")
    parser.add_argument("--nav-repo", type=Path, default=DEFAULT_NAV_REPO)
    parser.add_argument("--artifact-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    nav_repo = args.nav_repo.expanduser().resolve()
    stamp = utc_stamp()
    artifact_dir = (args.artifact_dir or nav_repo / "milestones" / "mordor_menu_button_qa" / stamp).expanduser().resolve()
    screenshots_dir = artifact_dir / "screenshots"
    notebooks_dir = artifact_dir / "notebooks"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    notebooks_dir.mkdir(parents=True, exist_ok=True)

    notebook_path = create_notebook(nav_repo, f"mordor_menu_button_{stamp}")
    result: dict[str, Any] = {
        "ok": False,
        "artifact_dir": str(artifact_dir),
        "notebook": str(notebook_path),
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1440, "height": 1050})
        try:
            open_notebook(
                page,
                base_url=args.base_url,
                jupyter_prefix="/" + args.jupyter_prefix.strip("/"),
                nav_repo=nav_repo,
                notebook_path=notebook_path,
            )
            menu_visible = "Mordor" in page.locator("body").inner_text(timeout=30_000)
            click_mordor_button(page)
            panel_visible = page.locator("[data-mordor-product-panel]").is_visible(timeout=30_000)
            prompt_result = send_prompt(page, notebook_path, screenshots_dir / "mordor_menu_button.png")
            result.update(
                {
                    "menu_or_toolbar_text_visible": menu_visible,
                    "panel_visible_after_button": panel_visible,
                    "prompt_result": prompt_result,
                }
            )
            result["ok"] = bool(
                menu_visible
                and panel_visible
                and prompt_result.get("status_done")
                and prompt_result.get("latest_trade_date_visible")
                and not any(cell.get("role") == "mordor_panel_bootstrap" for cell in prompt_result.get("mordor_cells", []))
                and not any(
                    "open Mordor Notebook panel" in str(cell.get("first_line", ""))
                    for cell in prompt_result.get("mordor_cells", [])
                )
            )
        finally:
            browser.close()

    shutil.copy2(notebook_path, notebooks_dir / notebook_path.name)
    write_json(artifact_dir / "summary.json", result)
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
