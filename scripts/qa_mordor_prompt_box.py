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
    if fallback_python.exists() and os.environ.get("MORDOR_PROMPT_BOX_QA_REEXEC") != "1":
        env = os.environ.copy()
        env["MORDOR_PROMPT_BOX_QA_REEXEC"] = "1"
        os.execve(str(fallback_python), [str(fallback_python), __file__, *sys.argv[1:]], env)
    raise


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def create_notebook(nav_repo: Path, name: str, goal: str) -> Path:
    notebook_path = nav_repo / "notebooks" / "qa_scratch" / f"{name}.ipynb"
    bootstrap = f"""from mordornotebook import attach

mordor = attach(
    repo={str(nav_repo)!r},
    goal={goal!r},
)
mordor.panel()
"""
    nb = new_notebook(
        cells=[new_code_cell(bootstrap)],
        metadata={
            "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
        },
    )
    notebook_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, notebook_path)
    return notebook_path


def output_kinds(cell: Any) -> list[str]:
    kinds: list[str] = []
    for output in cell.get("outputs", []) or []:
        output_type = output.get("output_type")
        if output_type:
            kinds.append(str(output_type))
        data = output.get("data") or {}
        kinds.extend(str(key) for key in data)
    return sorted(set(kinds))


def saved_mordor_cells(notebook_path: Path) -> list[dict[str, Any]]:
    saved = nbformat.read(notebook_path, as_version=4)
    return [
        {
            "cell_type": cell.cell_type,
            "first_line": str(cell.get("source", "")).splitlines()[0] if str(cell.get("source", "")).splitlines() else "",
            "output_count": len(cell.get("outputs", []) or []),
            "output_kinds": output_kinds(cell),
        }
        for cell in saved.cells
        if cell.get("metadata", {}).get("mordor")
    ]


def open_notebook_and_panel(
    *,
    page: Page,
    base_url: str,
    jupyter_prefix: str,
    nav_repo: Path,
    notebook_path: Path,
) -> None:
    notebook_rel = notebook_path.relative_to(nav_repo / "notebooks").as_posix()
    page.goto(f"{base_url.rstrip('/')}{jupyter_prefix}/lab/tree/{notebook_rel}?reset", wait_until="domcontentloaded", timeout=60_000)
    page.locator(".jp-Notebook:visible").first.wait_for(timeout=60_000)
    page.wait_for_function("() => !!window.mordorNotebookLab", timeout=60_000)

    cell = page.locator(".jp-Notebook .jp-CodeCell").first
    cell.scroll_into_view_if_needed(timeout=10_000)
    cell.locator(".cm-content").click(timeout=30_000)
    run_result = page.evaluate("() => window.mordorNotebookLab.runActiveCell()")
    if not run_result or not run_result.get("ok"):
        raise RuntimeError(f"Bootstrap cell did not execute cleanly: {run_result}")
    page.locator("[data-mordor-product-panel]").wait_for(timeout=120_000)


def send_prompt_on_current_page(
    *,
    page: Page,
    notebook_path: Path,
    prompt: str,
    expected_text: str | list[str],
    screenshot_path: Path,
    expected_status: str = "Done",
    required_output_kind: str | None = None,
    deadline_seconds: float = 780,
) -> dict[str, Any]:
    panel_before = page.locator("[data-mordor-product-panel]").inner_text(timeout=30_000)
    forbidden = [label for label in ("Start Codex", "Capture", "Insert Audit", "Ops") if label in panel_before]

    page.locator("[data-mordor-prompt]").fill(prompt, timeout=30_000)
    page.locator("[data-mordor-send]").click(timeout=30_000)
    expected_values = [expected_text] if isinstance(expected_text, str) else expected_text
    deadline = time.time() + deadline_seconds
    panel_after = ""
    body_text = ""
    mordor_cells: list[dict[str, Any]] = []
    status_matches = False
    expected_visible = False
    output_kind_present = False
    while time.time() < deadline:
        panel_after = page.locator("[data-mordor-product-panel]").inner_text(timeout=30_000)
        body_text = page.locator("body").inner_text(timeout=30_000)
        mordor_cells = saved_mordor_cells(notebook_path)
        status_matches = f"Status: {expected_status}" in panel_after
        expected_visible = all(value in body_text for value in expected_values)
        output_kind_present = (
            True
            if required_output_kind is None
            else any(required_output_kind in cell.get("output_kinds", []) for cell in mordor_cells)
        )
        if status_matches and expected_visible and output_kind_present:
            break
        time.sleep(1.0)

    ctx = page.evaluate("() => window.mordorNotebookLab.currentNotebook()")
    page.screenshot(path=str(screenshot_path), full_page=True)
    return {
        "ok": status_matches and expected_visible and output_kind_present and not forbidden,
        "notebook": str(notebook_path),
        "status": expected_status,
        "status_matches": status_matches,
        "expected_visible": expected_visible,
        "required_output_kind": required_output_kind,
        "output_kind_present": output_kind_present,
        "forbidden_controls": forbidden,
        "context": ctx,
        "mordor_cells": mordor_cells,
        "panel_after": panel_after,
        "screenshot": str(screenshot_path),
    }


def run_prompt_case(
    *,
    page: Page,
    base_url: str,
    jupyter_prefix: str,
    nav_repo: Path,
    notebook_path: Path,
    prompt: str,
    expected_text: str | list[str],
    screenshot_path: Path,
    expected_status: str = "Done",
    required_output_kind: str | None = None,
    deadline_seconds: float = 780,
) -> dict[str, Any]:
    open_notebook_and_panel(
        page=page,
        base_url=base_url,
        jupyter_prefix=jupyter_prefix,
        nav_repo=nav_repo,
        notebook_path=notebook_path,
    )
    return send_prompt_on_current_page(
        page=page,
        notebook_path=notebook_path,
        prompt=prompt,
        expected_text=expected_text,
        screenshot_path=screenshot_path,
        expected_status=expected_status,
        required_output_kind=required_output_kind,
        deadline_seconds=deadline_seconds,
    )


def add_local_storage_init(context: Any, settings: dict[str, str]) -> None:
    if not settings:
        return
    script = "\n".join(
        f"window.localStorage.setItem({json.dumps(str(key))}, {json.dumps(str(value))});"
        for key, value in settings.items()
    )
    context.add_init_script(script)


def run_cancel_case(
    *,
    page: Page,
    base_url: str,
    jupyter_prefix: str,
    nav_repo: Path,
    notebook_path: Path,
    prompt: str,
    screenshot_path: Path,
) -> dict[str, Any]:
    open_notebook_and_panel(
        page=page,
        base_url=base_url,
        jupyter_prefix=jupyter_prefix,
        nav_repo=nav_repo,
        notebook_path=notebook_path,
    )
    panel_before = page.locator("[data-mordor-product-panel]").inner_text(timeout=30_000)
    forbidden = [label for label in ("Start Codex", "Capture", "Insert Audit", "Ops") if label in panel_before]

    page.locator("[data-mordor-prompt]").fill(prompt, timeout=30_000)
    page.locator("[data-mordor-send]").click(timeout=30_000)
    page.locator("[data-mordor-stop]").wait_for(state="visible", timeout=30_000)
    page.locator("[data-mordor-stop]").click(timeout=30_000)

    deadline = time.time() + 30
    panel_after = ""
    while time.time() < deadline:
        panel_after = page.locator("[data-mordor-product-panel]").inner_text(timeout=30_000)
        if "Status: Cancelled" in panel_after and "Request cancelled" in panel_after:
            break
        time.sleep(0.5)

    ctx = page.evaluate("() => window.mordorNotebookLab.currentNotebook()")
    page.screenshot(path=str(screenshot_path), full_page=True)
    return {
        "ok": "Status: Cancelled" in panel_after and "Request cancelled" in panel_after and not forbidden,
        "notebook": str(notebook_path),
        "status": "Cancelled",
        "status_matches": "Status: Cancelled" in panel_after,
        "expected_visible": "Request cancelled" in panel_after,
        "forbidden_controls": forbidden,
        "context": ctx,
        "mordor_cells": saved_mordor_cells(notebook_path),
        "panel_after": panel_after,
        "screenshot": str(screenshot_path),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Browser QA for the Mordor prompt-box notebook workflow.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5011")
    parser.add_argument("--jupyter-prefix", default="/jlab")
    parser.add_argument("--nav-repo", type=Path, default=DEFAULT_NAV_REPO)
    parser.add_argument("--artifact-dir", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    nav_repo = args.nav_repo.expanduser().resolve()
    stamp = utc_stamp()
    artifact_dir = (args.artifact_dir or nav_repo / "milestones" / "mordor_prompt_box_qa" / stamp).expanduser().resolve()
    screenshots_dir = artifact_dir / "screenshots"
    notebooks_dir = artifact_dir / "notebooks"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    notebooks_dir.mkdir(parents=True, exist_ok=True)

    fresh_notebook = create_notebook(nav_repo, f"mordor_prompt_box_fresh_{stamp}", "prompt-box QA fresh universe")
    agent_notebook = create_notebook(nav_repo, f"mordor_prompt_box_agent_{stamp}", "prompt-box QA hidden Codex")
    acceptance_notebook = create_notebook(nav_repo, f"mordor_prompt_box_acceptance_{stamp}", "prompt-box QA acceptance suite")
    fake_agent_notebook = create_notebook(nav_repo, f"mordor_prompt_box_fake_agent_{stamp}", "prompt-box QA fake agent")
    stall_notebook = create_notebook(nav_repo, f"mordor_prompt_box_stall_{stamp}", "prompt-box QA stall")
    cancel_notebook = create_notebook(nav_repo, f"mordor_prompt_box_cancel_{stamp}", "prompt-box QA cancel")

    fresh_prompt = "can you identify how to load an equity parquet that is fresh for the equity universer"
    agent_prompt = (
        "Create exactly one markdown notebook cell. Its first line must be '## Mordor generated: agent smoke'. "
        "The body must say 'The hidden Codex agent inserted this cell through the Mordor prompt box.' Do not create code cells."
    )
    memory_prompt = (
        "Inspect the registered panel object and insert a cell that shows a recent date slice for three symbols selected from the data."
    )
    chart_prompt = "Create a simple chart from the loaded panel that lets me visually inspect recent returns for a few names."
    missing_prompt = "Load a deliberately missing object named DOES_NOT_EXIST and show me what failed."
    fake_agent_prompt = "Use the managed agent path to insert one markdown notebook cell."
    stall_prompt = "Use the managed agent path and intentionally wait long enough for the panel to show a stalled request."
    cancel_prompt = "Use the managed agent path and wait until I cancel this request."
    results: dict[str, Any] = {
        "ok": False,
        "artifact_dir": str(artifact_dir),
        "cases": {},
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 1050})
        page = context.new_page()
        try:
            results["cases"]["fresh_universe"] = run_prompt_case(
                page=page,
                base_url=args.base_url,
                jupyter_prefix="/" + args.jupyter_prefix.strip("/"),
                nav_repo=nav_repo,
                notebook_path=fresh_notebook,
                prompt=fresh_prompt,
                expected_text="latest_trade_date",
                screenshot_path=screenshots_dir / "fresh_universe.png",
            )
            results["cases"]["hidden_codex_agent"] = run_prompt_case(
                page=page,
                base_url=args.base_url,
                jupyter_prefix="/" + args.jupyter_prefix.strip("/"),
                nav_repo=nav_repo,
                notebook_path=agent_notebook,
                prompt=agent_prompt,
                expected_text="Mordor generated: agent smoke",
                screenshot_path=screenshots_dir / "hidden_codex_agent.png",
            )
            open_notebook_and_panel(
                page=page,
                base_url=args.base_url,
                jupyter_prefix="/" + args.jupyter_prefix.strip("/"),
                nav_repo=nav_repo,
                notebook_path=acceptance_notebook,
            )
            results["cases"]["acceptance_fresh_universe"] = send_prompt_on_current_page(
                page=page,
                notebook_path=acceptance_notebook,
                prompt=fresh_prompt,
                expected_text=["latest_trade_date", "2026-06-08"],
                screenshot_path=screenshots_dir / "acceptance_01_fresh_universe.png",
            )
            results["cases"]["acceptance_memory_slice"] = send_prompt_on_current_page(
                page=page,
                notebook_path=acceptance_notebook,
                prompt=memory_prompt,
                expected_text=["selected_symbols", "slice_rows"],
                screenshot_path=screenshots_dir / "acceptance_02_memory_slice.png",
            )
            results["cases"]["acceptance_chart"] = send_prompt_on_current_page(
                page=page,
                notebook_path=acceptance_notebook,
                prompt=chart_prompt,
                expected_text=["return_column", "symbols"],
                screenshot_path=screenshots_dir / "acceptance_03_chart.png",
                required_output_kind="image/png",
            )
            results["cases"]["acceptance_missing_object"] = send_prompt_on_current_page(
                page=page,
                notebook_path=acceptance_notebook,
                prompt=missing_prompt,
                expected_text=["DOES_NOT_EXIST", "Mordor could not find object"],
                screenshot_path=screenshots_dir / "acceptance_04_missing_object.png",
                expected_status="Failed",
                required_output_kind="error",
            )
        finally:
            context.close()

        fake_context = browser.new_context(viewport={"width": 1440, "height": 1050})
        add_local_storage_init(fake_context, {"mordorCodexCommand": "__mordor_fake_agent__"})
        fake_page = fake_context.new_page()
        try:
            results["cases"]["deterministic_fake_agent"] = run_prompt_case(
                page=fake_page,
                base_url=args.base_url,
                jupyter_prefix="/" + args.jupyter_prefix.strip("/"),
                nav_repo=nav_repo,
                notebook_path=fake_agent_notebook,
                prompt=fake_agent_prompt,
                expected_text="Mordor generated: fake agent",
                screenshot_path=screenshots_dir / "deterministic_fake_agent.png",
                deadline_seconds=45,
            )
        finally:
            fake_context.close()

        stall_context = browser.new_context(viewport={"width": 1440, "height": 1050})
        add_local_storage_init(
            stall_context,
            {
                "mordorCodexCommand": "__mordor_fake_agent_stall__",
                "mordorAgentStallMs": "1000",
                "mordorAgentTimeoutMs": "4500",
            },
        )
        stall_page = stall_context.new_page()
        try:
            results["cases"]["deterministic_stall_timeout"] = run_prompt_case(
                page=stall_page,
                base_url=args.base_url,
                jupyter_prefix="/" + args.jupyter_prefix.strip("/"),
                nav_repo=nav_repo,
                notebook_path=stall_notebook,
                prompt=stall_prompt,
                expected_text=["No new notebook cells", "timeout"],
                screenshot_path=screenshots_dir / "deterministic_stall_timeout.png",
                expected_status="Failed",
                deadline_seconds=30,
            )
        finally:
            stall_context.close()

        cancel_context = browser.new_context(viewport={"width": 1440, "height": 1050})
        add_local_storage_init(
            cancel_context,
            {
                "mordorCodexCommand": "__mordor_fake_agent_stall__",
                "mordorAgentStallMs": "1000",
                "mordorAgentTimeoutMs": "30000",
            },
        )
        cancel_page = cancel_context.new_page()
        try:
            results["cases"]["deterministic_cancel"] = run_cancel_case(
                page=cancel_page,
                base_url=args.base_url,
                jupyter_prefix="/" + args.jupyter_prefix.strip("/"),
                nav_repo=nav_repo,
                notebook_path=cancel_notebook,
                prompt=cancel_prompt,
                screenshot_path=screenshots_dir / "deterministic_cancel.png",
            )
        finally:
            cancel_context.close()
            browser.close()

    for path in (fresh_notebook, agent_notebook, acceptance_notebook, fake_agent_notebook, stall_notebook, cancel_notebook):
        shutil.copy2(path, notebooks_dir / path.name)
    results["ok"] = all(case.get("ok") for case in results["cases"].values())
    write_json(artifact_dir / "summary.json", results)
    print(json.dumps(results, indent=2, sort_keys=True, default=str))
    return 0 if results["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
