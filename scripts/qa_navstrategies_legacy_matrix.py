#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import uuid

DEFAULT_NAV_REPO = Path(os.environ.get("NAVSTRATEGIES_REPO", "~/repos/navstrategies")).expanduser()

try:
    import nbformat
    from nbformat.v4 import new_code_cell, new_markdown_cell
    from playwright.sync_api import Page, sync_playwright
except ModuleNotFoundError:
    fallback_python = DEFAULT_NAV_REPO / ".venv" / "bin" / "python"
    if fallback_python.exists() and os.environ.get("MORDOR_LEGACY_MATRIX_REEXEC") != "1":
        env = os.environ.copy()
        env["MORDOR_LEGACY_MATRIX_REEXEC"] = "1"
        os.execve(str(fallback_python), [str(fallback_python), __file__, *sys.argv[1:]], env)
    raise


DEFAULT_CHROMIUM = "/usr/bin/chromium-browser"
GENERATED_RENDER_MARKER = "# Mordor generated: legacy matrix render"
GENERATED_AUDIT_MARKER = "## Mordor generated: legacy matrix audit"

LEGACY_MATRIX: list[dict[str, str]] = [
    {
        "notebook": "00_malaal_universe_data.ipynb",
        "action": "Load/register hot universe panel; inspect latest date and symbol counts.",
        "proof": "DataFrame of latest stock/ETF universe rows.",
    },
    {
        "notebook": "01_peering_index_peer_set.ipynb",
        "action": "Inspect peer/index objects or insert loader cell if absent.",
        "proof": "Peer set table and one index comparison chart.",
    },
    {
        "notebook": "02_peering_basket_peer_set.ipynb",
        "action": "Inspect basket peer definitions and insert audit summary.",
        "proof": "Basket peer table.",
    },
    {
        "notebook": "03_drift_backtest_audit.ipynb",
        "action": "Register backtest panel/equity curve when present; insert drift audit.",
        "proof": "PnL/equity curve chart and top rows table.",
    },
    {
        "notebook": "04_tradeable_universe_last5y.ipynb",
        "action": "Load hot universe; insert date/ticker slice audit.",
        "proof": "Latest universe table.",
    },
    {
        "notebook": "05_earnings_event_audit.ipynb",
        "action": "Inspect earnings/event objects or insert bounded SEC event loader.",
        "proof": "Event-window table.",
    },
    {
        "notebook": "06_tradeable_universe_last5y_with_earnings.ipynb",
        "action": "Join/slice universe plus earnings events.",
        "proof": "Joined ticker/event table.",
    },
    {
        "notebook": "07_tradeable_universe_last5y_with_index_peer_context.ipynb",
        "action": "Inspect index and peer context columns.",
        "proof": "Ticker vs index/peer returns table or chart.",
    },
    {
        "notebook": "08_sf1_fcf_yield_ev_sanity_check.ipynb",
        "action": "Inspect SF1/EV/FCF frame; insert sanity audit.",
        "proof": "FCF yield sample table and chart.",
    },
    {
        "notebook": "09_sf1_fcf_yield_rank_backtest_pandas.ipynb",
        "action": "Inspect rank/backtest objects; insert bounded PnL audit.",
        "proof": "Rank sample table and PnL chart.",
    },
    {
        "notebook": "10_sf1_garp_matrix_cache.ipynb",
        "action": "Inspect matrix cache metadata and registered matrices.",
        "proof": "Matrix shape table and sample rows.",
    },
    {
        "notebook": "11_sf1_basic_daily_multiindex.ipynb",
        "action": "Validate MultiIndex slicing through Mordor helper.",
        "proof": "Date/ticker MultiIndex slice table.",
    },
    {
        "notebook": "M05_wikipedia_trends_explorer.ipynb",
        "action": "Inspect trend panels and insert sample page/ticker audit.",
        "proof": "Trend time series chart.",
    },
    {
        "notebook": "M06_fmp_sharadar_concat_demo.ipynb",
        "action": "Validate stock/ETF overlap load path without cold scan.",
        "proof": "Overlap sample table.",
    },
    {
        "notebook": "M27_sec_earnings_release_history_demo.ipynb",
        "action": "Inspect SEC history artifact and insert ticker audit.",
        "proof": "Recent filings table with links where available.",
    },
    {
        "notebook": "M27_sec_earnings_release_history_examples.ipynb",
        "action": "Run bounded examples through Mordor inserted cells.",
        "proof": "Example output table.",
    },
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def slug(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("_").lower()


def run(command: list[str], *, cwd: Path, timeout: float = 60.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, timeout=timeout, check=False)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, default=str) + "\n")


def normalize_notebook_ids(nb: Any) -> None:
    for cell in nb.cells:
        cell.setdefault("id", uuid.uuid4().hex[:8])


def create_qa_copy(nav_repo: Path, source_path: Path, dest_path: Path, matrix_row: dict[str, str]) -> dict[str, Any]:
    nb = nbformat.read(source_path, as_version=4)
    original_cell_count = len(nb.cells)
    normalize_notebook_ids(nb)
    bootstrap = f"""from mordornotebook import attach

legacy_matrix_source = {{
    "source_notebook": {str(source_path)!r},
    "qa_copy": {str(dest_path)!r},
    "notebook": {matrix_row["notebook"]!r},
    "required_action": {matrix_row["action"]!r},
    "required_render_proof": {matrix_row["proof"]!r},
    "original_cell_count": {original_cell_count},
}}

mordor = attach(
    repo={str(nav_repo)!r},
    goal="Legacy notebook matrix QA: {matrix_row["notebook"]}",
    notebook_path={str(dest_path)!r},
)
mordor.register("legacy_matrix_source", legacy_matrix_source)
mordor.panel()
"""
    nb.cells = [
        new_markdown_cell(
            "# Mordor Legacy Matrix QA\n\n"
            f"QA copy of `{matrix_row['notebook']}`. Original cells are preserved below but not run by the matrix harness."
        ),
        new_code_cell(bootstrap),
        *nb.cells,
    ]
    nb.metadata.setdefault("kernelspec", {"display_name": "Python 3", "language": "python", "name": "python3"})
    nb.metadata.setdefault("language_info", {"name": "python", "version": "3.12"})
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, dest_path)
    return {"original_cell_count": original_cell_count, "qa_cell_count": len(nb.cells)}


def audit_markdown(matrix_row: dict[str, str]) -> str:
    return (
        f"{GENERATED_AUDIT_MARKER}: {matrix_row['notebook']}\n\n"
        f"- Required action: {matrix_row['action']}\n"
        f"- Required render proof: {matrix_row['proof']}\n"
        "- Scope: bounded QA cells only; original legacy cells are preserved but not executed."
    )


def render_code(nav_repo: Path, notebook_path: Path, source_path: Path, matrix_row: dict[str, str]) -> str:
    safe_name = slug(matrix_row["notebook"]).replace(".", "_")
    return f"""{GENERATED_RENDER_MARKER}
from pathlib import Path
import json
import re

import matplotlib.pyplot as plt
import nbformat
import pandas as pd
from IPython.display import display

qa_notebook = Path({str(notebook_path)!r})
source_notebook = Path({str(source_path)!r})
required_action = {matrix_row["action"]!r}
required_render_proof = {matrix_row["proof"]!r}

nb = nbformat.read(qa_notebook, as_version=4)
source_text = "\\n".join(str(cell.get("source", "")) for cell in nb.cells)
tokens = [
    "ticker", "date", "return", "volume", "universe", "peer", "index", "basket",
    "earnings", "sec", "sf1", "fcf", "yield", "rank", "matrix", "trend", "cache",
]
token_rows = [{{"token": token, "count": len(re.findall(token, source_text, flags=re.IGNORECASE))}} for token in tokens]
legacy_matrix_token_counts = pd.DataFrame(token_rows).sort_values(["count", "token"], ascending=[False, True])
cell_type_counts = pd.Series([cell.cell_type for cell in nb.cells]).value_counts().rename_axis("cell_type").reset_index(name="count")

legacy_matrix_summary = pd.DataFrame(
    [
        {{
            "notebook": {matrix_row["notebook"]!r},
            "source_notebook": str(source_notebook),
            "qa_copy": str(qa_notebook),
            "required_action": required_action,
            "required_render_proof": required_render_proof,
            "cell_count": len(nb.cells),
            "code_cells": int((cell_type_counts.loc[cell_type_counts["cell_type"].eq("code"), "count"]).sum()),
            "markdown_cells": int((cell_type_counts.loc[cell_type_counts["cell_type"].eq("markdown"), "count"]).sum()),
            "generated_cells": sum("Mordor generated" in str(cell.get("source", "")) for cell in nb.cells),
        }}
    ]
)

display(legacy_matrix_summary)
display(legacy_matrix_token_counts.head(12))

fig, ax = plt.subplots(figsize=(8, 3.5))
plot_frame = legacy_matrix_token_counts.head(10).sort_values("count")
ax.barh(plot_frame["token"], plot_frame["count"], color="#3b82f6")
ax.set_title("Legacy matrix source audit: {matrix_row["notebook"]}")
ax.set_xlabel("source token count")
ax.grid(axis="x", alpha=0.25)
plt.tight_layout()
plt.show()

if "mordor" in globals():
    try:
        mordor.register(
            "legacy_matrix_audit_{safe_name[:48]}",
            {{
                "summary": legacy_matrix_summary.to_dict("records"),
                "token_counts": legacy_matrix_token_counts.head(20).to_dict("records"),
            }},
        )
    except Exception as exc:
        print("Mordor register skipped:", exc)
"""


def open_notebook(page: Page, base_url: str, prefix: str, workspace_id: str, notebook_rel: str) -> Any:
    page.goto(
        f"{base_url}{prefix}/lab/workspaces/{workspace_id}/tree/{notebook_rel}?reset",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    notebook = page.locator(".jp-Notebook:visible").first
    notebook.wait_for(timeout=60_000)
    return notebook


def bootstrap_panel(page: Page, notebook: Any) -> dict[str, Any]:
    before_cells = notebook.locator(".jp-Cell").count()
    bootstrap_error: str | None = None
    page.wait_for_function(
        """() => {
            const text = document.body ? document.body.innerText : "";
            return text.includes("Idle") && !text.includes("Unknown");
        }""",
        timeout=90_000,
    )
    page.keyboard.press("Escape")
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
            return out && out.textContent.includes('legacy_matrix_source');
        }""",
        timeout=30_000,
    )
    context_output = page.locator("[data-mordor-output]").inner_text(timeout=10_000)
    return {
        "before_cells": before_cells,
        "context_has_legacy_matrix_source": "legacy_matrix_source" in context_output,
        "context_chars": len(context_output),
    }


def summarize_insert_proc(proc: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    result: dict[str, Any] = {"returncode": proc.returncode}
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        result["stdout"] = proc.stdout[-4_000:]
        result["stderr"] = proc.stderr[-4_000:]
        return result
    operation = payload.get("operation") or {}
    notebook_insert = payload.get("notebook_insert") or {}
    result.update(
        {
            "ok": payload.get("ok"),
            "applied_live": payload.get("applied_live"),
            "persisted_notebook": payload.get("persisted_notebook"),
            "operation_id": operation.get("id"),
            "operation_status": operation.get("status"),
            "cell_type": operation.get("cell_type"),
            "inserted_index": notebook_insert.get("inserted_index"),
            "cell_count": notebook_insert.get("cell_count"),
            "stderr": proc.stderr[-1_000:] if proc.stderr else "",
        }
    )
    return result


def notebook_generated_counts(path: Path) -> dict[str, int]:
    nb = nbformat.read(path, as_version=4)
    sources = [str(cell.get("source", "")) for cell in nb.cells]
    return {
        "generated_total": sum("Mordor generated" in source for source in sources),
        "audit": sum(GENERATED_AUDIT_MARKER in source for source in sources),
        "render": sum(GENERATED_RENDER_MARKER in source for source in sources),
    }


def execute_render_cell(page: Page) -> None:
    render_cell = page.locator(".jp-CodeCell").last
    render_cell.scroll_into_view_if_needed(timeout=30_000)
    render_cell.click(timeout=30_000)
    handle = render_cell.element_handle(timeout=30_000)
    page.evaluate("(cell) => cell.setAttribute('data-mordor-render-target', '1')", handle)

    ready_js = """() => {
            const target = document.querySelector('[data-mordor-render-target="1"]');
            return target && (
                target.querySelector('img') ||
                target.querySelectorAll('.jp-OutputArea-output').length >= 3
            );
        }"""

    def wait_ready(timeout_ms: int) -> bool:
        try:
            page.wait_for_function(ready_js, timeout=timeout_ms)
            return True
        except Exception:
            return False

    attempts = [
        lambda: page.keyboard.press("Control+Enter"),
        lambda: page.keyboard.press("Shift+Enter"),
        lambda: page.locator("[data-command='notebook:run-cell']").first.click(timeout=5_000),
        lambda: page.locator("button[title^='Run']").first.click(timeout=5_000),
        lambda: (
            page.keyboard.press("Control+Shift+C"),
            time.sleep(0.4),
            page.keyboard.type("Run Selected Cells"),
            page.keyboard.press("Enter"),
        ),
    ]
    last_error: str | None = None
    for trigger in attempts:
        render_cell.scroll_into_view_if_needed(timeout=30_000)
        render_cell.click(timeout=30_000)
        try:
            trigger()
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        if wait_ready(20_000):
            break
    else:
        raise TimeoutError(f"render cell did not produce output after execution attempts; last_error={last_error}")

    page.wait_for_function(
        """() => document.querySelectorAll('.jp-CodeCell.jp-mod-running').length === 0""",
        timeout=90_000,
    )


def output_kinds(cell: Any) -> list[str]:
    kinds: list[str] = []
    for output in cell.get("outputs", []) or []:
        output_type = output.get("output_type")
        if output_type:
            kinds.append(str(output_type))
        data = output.get("data") or {}
        kinds.extend(str(key) for key in data)
    return sorted(set(kinds))


def final_notebook_evidence(path: Path) -> dict[str, Any]:
    nb = nbformat.read(path, as_version=4)
    generated_cells = []
    source_counts: dict[str, int] = {}
    for index, cell in enumerate(nb.cells):
        source = str(cell.get("source", ""))
        if "Mordor generated" not in source:
            continue
        source_counts[source] = source_counts.get(source, 0) + 1
        first_line = source.splitlines()[0] if source.splitlines() else ""
        generated_cells.append(
            {
                "index": index,
                "cell_type": cell.cell_type,
                "first_line": first_line,
                "output_count": len(cell.get("outputs", []) or []),
                "output_kinds": output_kinds(cell),
            }
        )
    return {
        "generated_cells": generated_cells,
        "generated_cell_count": len(generated_cells),
        "duplicate_generated_sources": sum(1 for count in source_counts.values() if count > 1),
        "render_output": any(
            GENERATED_RENDER_MARKER in str(cell.get("source", "")) and len(cell.get("outputs", []) or []) > 0
            for cell in nb.cells
        ),
        "table_output": any("text/html" in row["output_kinds"] for row in generated_cells),
        "chart_output": any("image/png" in row["output_kinds"] for row in generated_cells),
    }


def raw_bridge_requests(urls: list[str]) -> list[str]:
    from urllib.parse import urlparse

    bad = []
    for url in urls:
        parsed = urlparse(url)
        if (
            parsed.hostname == "127.0.0.1"
            and parsed.port not in {5011, 5012, 8890}
            and any(part in parsed.path for part in ("/context", "/memory", "/cell", "/agent", "/ops"))
        ):
            bad.append(url)
    return bad


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded Mordor QA over copied navstrategies legacy notebooks.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5011")
    parser.add_argument("--jupyter-prefix", default="/jlab")
    parser.add_argument("--nav-repo", type=Path, default=DEFAULT_NAV_REPO)
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--chromium", default=DEFAULT_CHROMIUM)
    parser.add_argument("--limit", type=int, default=0, help="Optional limit for incremental debugging.")
    parser.add_argument("--only", action="append", default=[], help="Run only notebooks whose filename contains this value.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    nav_repo = args.nav_repo.expanduser().resolve()
    stamp = utc_stamp()
    artifact_dir = (args.artifact_dir or nav_repo / "milestones" / "mordor_remote_qa" / stamp).expanduser().resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    screenshots_dir = artifact_dir / "screenshots"
    notebooks_dir = artifact_dir / "notebooks"
    temp_cells_dir = artifact_dir / "cell_sources"
    for path in (screenshots_dir, notebooks_dir, temp_cells_dir):
        path.mkdir(parents=True, exist_ok=True)

    mordorctl = nav_repo / ".venv" / "bin" / "mordorctl"
    legacy_rows = LEGACY_MATRIX[: args.limit] if args.limit else LEGACY_MATRIX
    if args.only:
        needles = [value.lower() for value in args.only]
        legacy_rows = [row for row in legacy_rows if any(needle in row["notebook"].lower() for needle in needles)]
        if not legacy_rows:
            raise SystemExit(f"No legacy notebooks matched --only values: {args.only}")
    scratch_root = nav_repo / "notebooks" / "qa_scratch" / "legacy_matrix" / stamp
    scratch_root.mkdir(parents=True, exist_ok=True)
    base_url = args.base_url.rstrip("/")
    prefix = "/" + args.jupyter_prefix.strip("/")
    summary: dict[str, Any] = {
        "ok": False,
        "artifact_dir": str(artifact_dir),
        "base_url": base_url,
        "jupyter_prefix": prefix,
        "scratch_root": str(scratch_root),
        "legacy_notebooks": [],
        "failures": [],
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path=args.chromium,
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        try:
            for idx, row in enumerate(legacy_rows, start=1):
                name = row["notebook"]
                name_slug = slug(name)
                source_path = nav_repo / "notebooks" / "legacy" / name
                copy_path = scratch_root / name
                notebook_rel = copy_path.relative_to(nav_repo / "notebooks").as_posix()
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                request_urls: list[str] = []
                console_errors: list[str] = []
                page.on("request", lambda request, urls=request_urls: urls.append(request.url))
                page.on("console", lambda msg, errors=console_errors: errors.append(msg.text) if msg.type == "error" else None)
                result: dict[str, Any] = {
                    "notebook": name,
                    "source_notebook": str(source_path),
                    "qa_copy": str(copy_path),
                    "status": "fail",
                    "error": None,
                    "screenshot": str(screenshots_dir / f"{name_slug}.png"),
                    "final_notebook": str(notebooks_dir / name),
                    "required_action": row["action"],
                    "required_render_proof": row["proof"],
                }
                try:
                    if not source_path.exists():
                        raise FileNotFoundError(str(source_path))
                    copy_meta = create_qa_copy(nav_repo, source_path, copy_path, row)
                    shutil.copy2(copy_path, notebooks_dir / f"starting_{name}")
                    workspace = f"mordor-legacy-{stamp.lower()}-{idx:02d}"
                    notebook = open_notebook(page, base_url, prefix, workspace, notebook_rel)
                    bootstrap = bootstrap_panel(page, notebook)

                    audit_path = temp_cells_dir / f"{name_slug}_audit.md"
                    render_path = temp_cells_dir / f"{name_slug}_render.py"
                    audit_path.write_text(audit_markdown(row), encoding="utf-8")
                    render_path.write_text(render_code(nav_repo, copy_path, source_path, row), encoding="utf-8")

                    audit_proc = run(
                        [str(mordorctl), "cell", "insert", "--type", "markdown", "--file", str(audit_path), "--json"],
                        cwd=nav_repo,
                        timeout=30,
                    )
                    render_proc = run(
                        [str(mordorctl), "cell", "insert", "--type", "code", "--file", str(render_path), "--json"],
                        cwd=nav_repo,
                        timeout=30,
                    )
                    result["insert_audit"] = summarize_insert_proc(audit_proc)
                    result["insert_render"] = summarize_insert_proc(render_proc)
                    if audit_proc.returncode != 0 or render_proc.returncode != 0:
                        raise RuntimeError("mordorctl insert failed")

                    persisted = notebook_generated_counts(copy_path)
                    if persisted != {"audit": 1, "generated_total": 2, "render": 1}:
                        raise RuntimeError(f"expected exactly one audit and one render cell after insert: {persisted}")

                    notebook = open_notebook(page, base_url, prefix, f"{workspace}-verify", notebook_rel)
                    page.locator(f"text={GENERATED_RENDER_MARKER}").wait_for(timeout=60_000)
                    execute_render_cell(page)
                    page.keyboard.press("Control+S")
                    time.sleep(2.5)
                    page.screenshot(path=result["screenshot"], full_page=True)
                    shutil.copy2(copy_path, result["final_notebook"])
                    evidence = final_notebook_evidence(copy_path)
                    bad_requests = raw_bridge_requests(request_urls)
                    result.update(
                        {
                            "status": "pass",
                            "copy_meta": copy_meta,
                            "bootstrap": bootstrap,
                            "persisted": persisted,
                            "evidence": evidence,
                            "console_error_count": len(console_errors),
                            "raw_bridge_requests": bad_requests,
                        }
                    )
                    if evidence["generated_cell_count"] != 2 or evidence["duplicate_generated_sources"]:
                        raise RuntimeError(f"duplicate or unexpected generated cells: {evidence}")
                    if not evidence["render_output"] or not evidence["table_output"] or not evidence["chart_output"]:
                        raise RuntimeError(f"missing render evidence: {evidence}")
                    if bad_requests:
                        raise RuntimeError(f"raw bridge requests detected: {bad_requests[:3]}")
                except Exception as exc:
                    result["status"] = "fail"
                    result["error"] = f"{type(exc).__name__}: {exc}"
                    try:
                        page.screenshot(path=result["screenshot"], full_page=True)
                    except Exception:
                        pass
                    summary["failures"].append({"notebook": name, "error": result["error"]})
                finally:
                    page.close()
                    summary["legacy_notebooks"].append(result)
                    write_json(artifact_dir / "summary.json", summary)
        finally:
            browser.close()

    summary["ok"] = all(row["status"] == "pass" for row in summary["legacy_notebooks"])
    summary["passed"] = sum(row["status"] == "pass" for row in summary["legacy_notebooks"])
    summary["failed"] = sum(row["status"] != "pass" for row in summary["legacy_notebooks"])
    lines = [
        "# Mordor Legacy Notebook Matrix QA Summary",
        "",
        f"- ok: `{summary['ok']}`",
        f"- passed: `{summary['passed']}`",
        f"- failed: `{summary['failed']}`",
        "",
        "| Notebook | Status |",
        "|---|---|",
    ]
    for row in summary["legacy_notebooks"]:
        lines.append(f"| `{row['notebook']}` | `{row['status']}` |")
    if summary["failures"]:
        lines.extend(["", "## Failures", ""])
        lines.extend(f"- `{row['notebook']}`: {row['error']}" for row in summary["failures"])
    (artifact_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_json(artifact_dir / "summary.json", summary)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
