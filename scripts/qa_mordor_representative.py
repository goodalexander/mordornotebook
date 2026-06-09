#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

try:
    import nbformat
    from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook
    from playwright.sync_api import Page, sync_playwright
except ModuleNotFoundError:
    fallback = os.environ.get("MORDOR_REPRESENTATIVE_QA_PYTHON")
    if not fallback:
        repo_env = os.environ.get("MORDOR_REPO") or os.environ.get("MORDOR_DEFAULT_REPO")
        if repo_env:
            candidate = Path(repo_env).expanduser() / ".venv" / "bin" / "python"
            if candidate.exists():
                fallback = str(candidate)
    if fallback and os.environ.get("MORDOR_REPRESENTATIVE_QA_REEXEC") != "1":
        env = os.environ.copy()
        env["MORDOR_REPRESENTATIVE_QA_REEXEC"] = "1"
        os.execve(fallback, [fallback, __file__, *sys.argv[1:]], env)
    raise


APP_SOURCE_PATHS = [
    "mordornotebook/agent",
    "mordornotebook/config.py",
    "mordornotebook/labextension/static",
    "mordornotebook/labextension_src/src",
    "mordornotebook/server",
    "mordornotebook/ui.py",
]

ROUTER_FORBIDDEN = [
    "canHandle",
    "equityUniverseCells",
    "memoryInspectCells",
    "chartCells",
    "missingObjectCells",
    "recent returns chart",
    "fresh equity universe",
    "HotUniverseConfig",
    "DOES_NOT_EXIST",
]


@dataclass(frozen=True)
class Scenario:
    sid: str
    title: str
    prompt: str
    expected_terms: tuple[str, ...] = ()
    requires_chart: bool = False
    forbid_source_terms: tuple[str, ...] = ()


@dataclass
class CellSummary:
    index: int
    cell_type: str
    first_line: str
    role: str | None
    output_count: int
    output_kinds: list[str]
    has_error: bool
    has_image: bool
    source: str
    output_text: str


@dataclass
class RunResult:
    backend: str
    scenario: str
    ok: bool = False
    failure_reason: str = ""
    notebook_path: str = ""
    start_notebook: str = ""
    final_notebook: str = ""
    screenshot: str = ""
    manifest_path: str = ""
    transcript_paths: list[str] = field(default_factory=list)
    panel_done: bool = False
    panel_failed: bool = False
    generated_cell_count: int = 0
    markdown_cell_count: int = 0
    code_cell_count: int = 0
    code_output_count: int = 0
    chart_output_count: int = 0
    error_output_count: int = 0
    expected_terms_found: dict[str, bool] = field(default_factory=dict)
    browser_errors: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    request_id: str | None = None
    panel_text_tail: str = ""
    agent_log_tail: str = ""


SCENARIOS = [
    Scenario(
        sid="wikimedia_pageviews",
        title="Wikimedia Pageview Pull",
        prompt=(
            "Use the repository's Wikimedia helper or source client to pull daily pageview history "
            "for Peter Thiel, summarize latest coverage, show latest rows, and render a chart. "
            "Discover the helper from the repo. Do not use SQL, parquet, or local cache unless you "
            "explicitly state it is only for comparison. Keep the code bounded and reproducible."
        ),
        expected_terms=("Peter", "views", "latest"),
        requires_chart=True,
        forbid_source_terms=("duckdb", "sqlite", "read_parquet", "wiki__attention"),
    ),
    Scenario(
        sid="fresh_equity_panel",
        title="Fresh Equity Panel Load",
        prompt=(
            "Find the current efficient Parquet-based equity or ETF panel loader in this repo. "
            "Load a bounded fresh sample and display coverage, columns, date range, symbol count, "
            "and a few liquid symbols. Register the loaded object in Mordor memory if useful. "
            "Do not fall back to CSV unless the repo documents that as current."
        ),
        expected_terms=("symbol", "date", "rows"),
        forbid_source_terms=("read_csv",),
    ),
    Scenario(
        sid="sharadar_liquidity",
        title="Sharadar SEP / Daily Liquidity Slice",
        prompt=(
            "Using the repository's current Sharadar SEP or daily panel artifacts, compute a bounded "
            "recent liquidity slice and show median dollar volume coverage for recent dates. "
            "Discover artifact locations from repo code or docs, include provenance, and do not use SQL."
        ),
        expected_terms=("volume", "dollar", "date"),
        forbid_source_terms=("duckdb", "sqlite", "select "),
    ),
    Scenario(
        sid="sec_filing_provenance",
        title="SEC Extraction / Filing Provenance",
        prompt=(
            "Inspect the repository's SEC extraction pipeline artifacts and show recent filing "
            "provenance for a small ticker set such as AAPL, NVDA, TSM, and UAL. Distinguish feed, "
            "accession, filing index page, primary document, exhibits, parse state, extraction state, "
            "and freshness timestamps when available. Report missing data explicitly."
        ),
        expected_terms=("accession", "filing", "state"),
    ),
    Scenario(
        sid="fmp_transcript_coverage",
        title="FMP Transcript Coverage",
        prompt=(
            "Find the repository's FMP transcript storage or access path. Inspect recent transcript "
            "coverage for a small ticker set such as AAPL, NVDA, MSFT, and META, and display date, "
            "quarter/year, and body availability. Report endpoint/local mismatches as mismatches, "
            "not stale data unless proven."
        ),
        expected_terms=("transcript", "quarter", "date"),
    ),
    Scenario(
        sid="fred_macro_chart",
        title="FRED Macro Series Chart",
        prompt=(
            "Use the repository's FRED access pattern to pull a small set of macro series, including "
            "a long rate and inflation series if available. Display series ids, latest dates, latest "
            "values, and render a chart. State any transformations explicitly and make missing "
            "credential failures visible."
        ),
        expected_terms=("series", "latest", "FRED"),
        requires_chart=True,
    ),
    Scenario(
        sid="tbpn_style_screen",
        title="Cross-Sectional Screen / TBPN-Style Prep",
        prompt=(
            "Using current panel artifacts, build a bounded cross-sectional screen with market-cap "
            "change and dollar-volume style features, rank or z-score them, and display top rows with "
            "ticker names. Discover the tickers/name-labeling source from repo code or docs. Explain "
            "feature definitions and lookback dates. Do not use SQL unless repo docs prove it is the "
            "only current source."
        ),
        expected_terms=("ticker", "rank", "name"),
        forbid_source_terms=("duckdb", "sqlite", "select "),
    ),
    Scenario(
        sid="bounded_backtest_event",
        title="Simple Backtest / Event Window Inspection",
        prompt=(
            "Using a bounded subset of current panel data, create a simple inspectable signal or "
            "event-window check. Display assumptions, no-lookahead constraints, summary metrics, and "
            "render a PnL or event chart. Keep runtime and memory bounded and make the generated cells "
            "reproducible."
        ),
        expected_terms=("return", "summary", "assumption"),
        requires_chart=True,
    ),
]


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")


def run_command(args: list[str], *, cwd: Path, timeout: float = 20.0) -> dict[str, Any]:
    proc = subprocess.run(args, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)
    return {
        "args": args,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
        "ok": proc.returncode == 0,
    }


def read_http_json(url: str, timeout: float = 10.0) -> dict[str, Any]:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def audit_source_invariants(mordor_repo: Path, repo_under_test: Path) -> dict[str, Any]:
    checked_files: list[str] = []
    findings: list[dict[str, str]] = []
    forbidden = [str(repo_under_test), *ROUTER_FORBIDDEN]
    for rel in APP_SOURCE_PATHS:
        path = mordor_repo / rel
        if path.is_file():
            files = [path]
        elif path.is_dir():
            files = [p for p in path.rglob("*") if p.is_file()]
        else:
            continue
        for file_path in files:
            if any(part in {"node_modules", "__pycache__"} for part in file_path.parts):
                continue
            if file_path.suffix in {".pyc", ".pyo"}:
                continue
            text = file_path.read_text(encoding="utf-8", errors="replace")
            checked_files.append(str(file_path))
            for term in forbidden:
                if term and term in text:
                    findings.append({"file": str(file_path), "term": term})
    return {"ok": not findings, "checked_files": checked_files, "findings": findings}


def create_starter_notebook(
    repo_under_test: Path,
    notebook_dir: Path,
    scenario: Scenario,
    backend: str,
    stamp: str,
) -> Path:
    notebook_path = notebook_dir / f"{scenario.sid}_{backend}.ipynb"
    title = (
        f"# Mordor Representative QA: {scenario.title} / {backend}\n\n"
        "This is a thin starter notebook. It contains no scenario analysis cells; "
        "Mordor must generate the audit/code cells during the QA run."
    )
    bootstrap = f"""# Mordor representative QA bootstrap
import os
from pathlib import Path
from mordornotebook import attach

def _discover_repo_root(start):
    start = Path(start).resolve()
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return str(candidate)
    return None

MORDOR_REPO = (
    os.environ.get("MORDOR_REPO")
    or os.environ.get("MORDOR_DEFAULT_REPO")
    or _discover_repo_root(Path.cwd())
)
if not MORDOR_REPO:
    raise RuntimeError("Could not discover the repo root from env or the notebook working directory.")

mordor = attach(
    repo=MORDOR_REPO,
    goal={json.dumps(f"Representative QA {stamp}: {scenario.sid} / {backend}")},
)
mordor.panel()
"""
    nb = new_notebook(
        cells=[new_markdown_cell(title), new_code_cell(bootstrap)],
        metadata={
            "kernelspec": {"display_name": "Python 3 (ipykernel)", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.12"},
            "mordor_representative_qa": {
                "scenario": scenario.sid,
                "backend": backend,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        },
    )
    notebook_path.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(nb, notebook_path)
    return notebook_path


def output_text(output: Any) -> str:
    output_type = output.get("output_type")
    if output_type == "stream":
        value = output.get("text", "")
        return "".join(value) if isinstance(value, list) else str(value)
    if output_type in {"display_data", "execute_result"}:
        data = output.get("data", {}) or {}
        parts: list[str] = []
        for key in ("text/plain", "text/html"):
            value = data.get(key)
            if isinstance(value, list):
                parts.append("".join(str(item) for item in value))
            elif value is not None:
                parts.append(str(value))
        return "\n".join(parts)
    if output_type == "error":
        traceback = output.get("traceback") or []
        return "\n".join(str(item) for item in traceback) or f"{output.get('ename', '')}: {output.get('evalue', '')}"
    return ""


def output_kinds(output: Any) -> list[str]:
    kinds: list[str] = []
    output_type = output.get("output_type")
    if output_type:
        kinds.append(str(output_type))
    data = output.get("data") or {}
    kinds.extend(str(key) for key in data)
    return kinds


def notebook_cell_summaries(notebook_path: Path) -> list[CellSummary]:
    nb = nbformat.read(notebook_path, as_version=4)
    rows: list[CellSummary] = []
    for index, cell in enumerate(nb.cells):
        metadata = cell.get("metadata", {}).get("mordor")
        if not metadata:
            continue
        outputs = cell.get("outputs", []) or []
        kinds = sorted(set(kind for output in outputs for kind in output_kinds(output)))
        text = "\n".join(output_text(output) for output in outputs)
        source = str(cell.get("source", ""))
        rows.append(
            CellSummary(
                index=index,
                cell_type=str(cell.get("cell_type", "")),
                first_line=source.splitlines()[0] if source.splitlines() else "",
                role=metadata.get("role"),
                output_count=len(outputs),
                output_kinds=kinds,
                has_error=any(output.get("output_type") == "error" for output in outputs),
                has_image=any("image/png" in (output.get("data", {}) or {}) for output in outputs),
                source=source,
                output_text=text[:12000],
            )
        )
    return rows


def summarize_cells(cells: list[CellSummary]) -> dict[str, int]:
    code_cells = [cell for cell in cells if cell.cell_type == "code"]
    return {
        "generated_cell_count": len(cells),
        "markdown_cell_count": sum(cell.cell_type == "markdown" for cell in cells),
        "code_cell_count": len(code_cells),
        "code_output_count": sum(cell.output_count for cell in code_cells),
        "chart_output_count": sum(cell.has_image for cell in code_cells),
        "error_output_count": sum(cell.has_error for cell in code_cells),
    }


def browser_open_notebook(page: Page, *, base_url: str, jupyter_prefix: str, repo_under_test: Path, notebook_path: Path) -> None:
    notebook_rel = notebook_path.relative_to(repo_under_test / "notebooks").as_posix()
    url = f"{base_url.rstrip('/')}{jupyter_prefix}/lab/tree/{notebook_rel}?reset"
    page.goto(url, wait_until="domcontentloaded", timeout=60_000)
    page.locator(".jp-Notebook:visible").first.wait_for(timeout=60_000)
    page.wait_for_function("() => !!window.mordorNotebookLab && !!window.mordorNotebookLab.runActiveCell", timeout=60_000)


def run_bootstrap_cell(page: Page) -> dict[str, Any]:
    code_cell = page.locator(".jp-Notebook .jp-CodeCell").first
    code_cell.scroll_into_view_if_needed(timeout=10_000)
    code_cell.locator(".cm-content").click(timeout=30_000)
    return page.evaluate(
        """
        async () => await Promise.race([
          window.mordorNotebookLab.runActiveCell(),
          new Promise((resolve) => setTimeout(
            () => resolve({ok: false, error: 'bootstrap execution timed out in browser'}),
            60000
          ))
        ])
        """
    )


def configure_backend(context: Any, backend: str, agent_timeout_ms: int, agent_stall_ms: int) -> None:
    payload = json.dumps([backend, agent_timeout_ms, agent_stall_ms])
    context.add_init_script(
        f"""
        (() => {{
          const [backend, timeoutMs, stallMs] = {payload};
          window.localStorage.setItem('mordorAgentBackend', backend);
          window.localStorage.setItem('mordorCodexCommand', 'codex --sandbox danger-full-access --ask-for-approval never');
          window.localStorage.setItem('mordorCursorCommand', 'cursor-agent');
          window.localStorage.setItem('mordorCursorSandbox', 'disabled');
          window.localStorage.setItem('mordorAgentTimeoutMs', String(timeoutMs));
          window.localStorage.setItem('mordorAgentStallMs', String(stallMs));
        }})();
        """,
    )


def panel_text(page: Page) -> str:
    return page.locator("[data-mordor-product-panel]").inner_text(timeout=30_000)


def panel_log(page: Page) -> str:
    try:
        return page.locator("[data-mordor-log]").inner_text(timeout=5_000)
    except Exception:
        return ""


def safe_screenshot(page: Page, path: Path) -> None:
    page.screenshot(path=str(path), full_page=False, timeout=20_000)


def parse_request_id(log_text: str) -> str | None:
    try:
        payload = json.loads(log_text)
        value = payload.get("requestId")
        return str(value) if value else None
    except json.JSONDecodeError:
        return None


def transcript_candidates(started_at: float, request_id: str | None, backend: str) -> list[Path]:
    transcript_dir = Path.home() / ".local" / "state" / "mordornotebook" / "transcripts"
    if not transcript_dir.exists():
        return []
    candidates: list[Path] = []
    if request_id:
        session = f"mordor-{backend}-{request_id.replace('/', '-')}"
        candidates.extend(transcript_dir.glob(f"{session}*"))
    for path in transcript_dir.glob("*"):
        try:
            if path.stat().st_mtime >= started_at - 5:
                candidates.append(path)
        except FileNotFoundError:
            continue
    unique = {str(path): path for path in candidates if path.is_file()}
    return sorted(unique.values(), key=lambda path: path.stat().st_mtime)


def validation_transcript_text(path: Path, max_chars: int = 500_000) -> str:
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n... transcript truncated for validation ...\n" + text[-half:]


def validate_run(
    *,
    scenario: Scenario,
    cells: list[CellSummary],
    panel_after: str,
    agent_log_text: str,
    browser_errors: list[str],
    console_errors: list[str],
) -> tuple[bool, str, dict[str, bool]]:
    failures: list[str] = []
    combined_source = "\n".join(cell.source for cell in cells).lower()
    combined_output = "\n".join(cell.output_text for cell in cells).lower()
    combined_all = f"{combined_source}\n{combined_output}"
    expected = {term: term.lower() in combined_all for term in scenario.expected_terms}

    if "Status: Done" not in panel_after:
        failures.append("panel did not reach Status: Done")
    if browser_errors:
        failures.append(f"{len(browser_errors)} browser page error(s)")
    if console_errors:
        failures.append(f"{len(console_errors)} browser console error(s)")
    if not cells:
        failures.append("no Mordor-generated cells found in saved notebook")
    if not any(cell.cell_type == "markdown" for cell in cells):
        failures.append("no Mordor-generated markdown cell")
    if not any(cell.cell_type == "code" for cell in cells):
        failures.append("no Mordor-generated code cell")
    if any(cell.has_error for cell in cells if cell.cell_type == "code"):
        failures.append("generated code cell produced error output")
    if not any(cell.output_count > 0 for cell in cells if cell.cell_type == "code"):
        failures.append("generated code cells have no outputs")
    if scenario.requires_chart and not any(cell.has_image for cell in cells if cell.cell_type == "code"):
        failures.append("expected chart image output was not rendered")
    missing_terms = [term for term, found in expected.items() if not found]
    if missing_terms:
        failures.append("missing expected output/source terms: " + ", ".join(missing_terms))
    for term in scenario.forbid_source_terms:
        if term.lower() in combined_source:
            failures.append(f"forbidden generated source term present: {term}")
    first_line_failures = [
        cell.first_line
        for cell in cells
        if "mordor generated" not in cell.first_line.lower()
    ]
    if first_line_failures:
        failures.append("one or more generated cells do not start with 'Mordor generated'")
    insertion_markers = (
        "mordorctl cell insert",
        "notebook/cell",
        '"op_type": "insert_cell"',
        "'op_type': 'insert_cell'",
    )
    if not any(marker in agent_log_text for marker in insertion_markers):
        failures.append("transcript/log does not show Mordor cell insertion")

    return not failures, "; ".join(failures), expected


def run_one_case(
    *,
    playwright: Any,
    scenario: Scenario,
    backend: str,
    stamp: str,
    repo_under_test: Path,
    base_url: str,
    jupyter_prefix: str,
    work_notebook_dir: Path,
    artifact_dir: Path,
    agent_timeout_ms: int,
    agent_stall_ms: int,
) -> RunResult:
    screenshots_dir = artifact_dir / "screenshots"
    notebooks_dir = artifact_dir / "notebooks"
    transcripts_dir = artifact_dir / "transcripts"
    manifests_dir = artifact_dir / "manifests"
    for path in (screenshots_dir, notebooks_dir, transcripts_dir, manifests_dir):
        path.mkdir(parents=True, exist_ok=True)

    notebook_path = create_starter_notebook(repo_under_test, work_notebook_dir, scenario, backend, stamp)
    start_copy = notebooks_dir / f"{scenario.sid}_{backend}_start.ipynb"
    final_copy = notebooks_dir / f"{scenario.sid}_{backend}_final.ipynb"
    screenshot = screenshots_dir / f"{scenario.sid}_{backend}.png"
    manifest_path = manifests_dir / f"{scenario.sid}_{backend}.json"
    shutil.copy2(notebook_path, start_copy)

    result = RunResult(
        backend=backend,
        scenario=scenario.sid,
        notebook_path=str(notebook_path),
        start_notebook=str(start_copy),
        final_notebook=str(final_copy),
        screenshot=str(screenshot),
        manifest_path=str(manifest_path),
    )
    browser_errors: list[str] = []
    console_errors: list[str] = []
    started_at = time.time()

    browser = playwright.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1440, "height": 1050})
    configure_backend(context, backend, agent_timeout_ms, agent_stall_ms)
    page = context.new_page()
    page.on("pageerror", lambda exc: browser_errors.append(str(exc)))
    page.on(
        "console",
        lambda msg: console_errors.append(msg.text) if msg.type == "error" else None,
    )

    panel_after = ""
    log_text = ""
    try:
        browser_open_notebook(
            page,
            base_url=base_url,
            jupyter_prefix=jupyter_prefix,
            repo_under_test=repo_under_test,
            notebook_path=notebook_path,
        )
        bootstrap_result = run_bootstrap_cell(page)
        if not bootstrap_result or not bootstrap_result.get("ok"):
            raise RuntimeError(f"bootstrap cell failed: {bootstrap_result}")
        page.locator("[data-mordor-product-panel]").wait_for(timeout=120_000)
        page.locator("[data-mordor-agent-select]").select_option(backend)
        before = panel_text(page)
        forbidden_controls = [label for label in ("Start Codex", "Capture", "Insert Audit", "Ops") if label in before]
        if forbidden_controls:
            raise RuntimeError("legacy debug controls visible: " + ", ".join(forbidden_controls))

        page.locator("[data-mordor-prompt]").fill(scenario.prompt, timeout=30_000)
        page.locator("[data-mordor-send]").click(timeout=30_000)
        deadline = time.time() + (agent_timeout_ms / 1000) + 30
        while time.time() < deadline:
            panel_after = panel_text(page)
            log_text = panel_log(page)
            if "Status: Done" in panel_after or "Status: Failed" in panel_after or "Status: Cancelled" in panel_after:
                break
            time.sleep(2.0)
        safe_screenshot(page, screenshot)
    except Exception as exc:
        result.failure_reason = str(exc)
        try:
            safe_screenshot(page, screenshot)
        except Exception:
            pass
    finally:
        try:
            context.close()
        finally:
            browser.close()

    time.sleep(1.0)
    if notebook_path.exists():
        shutil.copy2(notebook_path, final_copy)

    request_id = parse_request_id(log_text)
    copied_transcripts: list[str] = []
    transcript_text_parts = [log_text]
    for transcript in transcript_candidates(started_at, request_id, backend):
        dest = transcripts_dir / f"{scenario.sid}_{backend}_{transcript.name}"
        try:
            shutil.copy2(transcript, dest)
            copied_transcripts.append(str(dest))
            transcript_text_parts.append(validation_transcript_text(dest))
        except OSError:
            continue

    cells = notebook_cell_summaries(notebook_path) if notebook_path.exists() else []
    counts = summarize_cells(cells)
    for key, value in counts.items():
        setattr(result, key, value)
    result.browser_errors = browser_errors
    result.console_errors = console_errors
    result.panel_done = "Status: Done" in panel_after
    result.panel_failed = "Status: Failed" in panel_after
    result.panel_text_tail = panel_after[-6000:]
    result.agent_log_tail = log_text[-12000:]
    result.request_id = request_id
    result.transcript_paths = copied_transcripts

    transcript_text = "\n".join(transcript_text_parts)
    validation_ok, validation_failure, expected = validate_run(
        scenario=scenario,
        cells=cells,
        panel_after=panel_after,
        agent_log_text=transcript_text,
        browser_errors=browser_errors,
        console_errors=console_errors,
    )
    result.expected_terms_found = expected
    if result.failure_reason:
        result.ok = False
        result.failure_reason = result.failure_reason + ("; " + validation_failure if validation_failure else "")
    else:
        result.ok = validation_ok
        result.failure_reason = validation_failure

    manifest = {
        **asdict(result),
        "scenario_title": scenario.title,
        "prompt": scenario.prompt,
        "cells": [asdict(cell) for cell in cells],
    }
    write_json(manifest_path, manifest)
    return result


def select_scenarios(values: list[str] | None) -> list[Scenario]:
    if not values:
        return SCENARIOS
    requested = set()
    for value in values:
        requested.update(part.strip() for part in value.split(",") if part.strip())
    by_id = {scenario.sid: scenario for scenario in SCENARIOS}
    missing = sorted(requested - set(by_id))
    if missing:
        raise SystemExit("Unknown scenario id(s): " + ", ".join(missing))
    return [scenario for scenario in SCENARIOS if scenario.sid in requested]


def select_backends(values: list[str] | None) -> list[str]:
    if not values:
        return ["codex", "cursor"]
    requested: list[str] = []
    for value in values:
        requested.extend(part.strip() for part in value.split(",") if part.strip())
    bad = [backend for backend in requested if backend not in {"codex", "cursor"}]
    if bad:
        raise SystemExit("Unknown backend(s): " + ", ".join(bad))
    return requested


def environment_audit(
    *,
    mordor_repo: Path,
    repo_under_test: Path,
    base_url: str,
    jupyter_prefix: str,
) -> dict[str, Any]:
    health_url = f"{base_url.rstrip('/')}{jupyter_prefix}/mordor/api/health"
    result: dict[str, Any] = {
        "health_url": health_url,
        "health": None,
        "health_ok": False,
        "commands": {},
        "repo_under_test": str(repo_under_test),
        "mordor_repo": str(mordor_repo),
    }
    try:
        health = read_http_json(health_url)
        result["health"] = health
        result["health_ok"] = bool(health.get("ok"))
    except (URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        result["health_error"] = str(exc)
    result["commands"]["codex"] = run_command(["bash", "-lc", "command -v codex && codex --version"], cwd=mordor_repo)
    result["commands"]["cursor"] = run_command(["bash", "-lc", "command -v cursor-agent && cursor-agent --version"], cwd=mordor_repo)
    result["ok"] = bool(
        result["health_ok"]
        and result["commands"]["codex"]["ok"]
        and result["commands"]["cursor"]["ok"]
    )
    return result


def write_source_grep(path: Path, source_audit: dict[str, Any]) -> None:
    lines = [
        "# Mordor Representative QA Source Invariant Audit",
        "",
        f"ok: {source_audit.get('ok')}",
        "",
        "## Findings",
        "",
    ]
    findings = source_audit.get("findings") or []
    if not findings:
        lines.append("No forbidden app-side repo paths or prompt-router strings found.")
    else:
        for finding in findings:
            lines.append(f"- {finding['file']}: {finding['term']}")
    lines.extend(["", "## Checked Files", ""])
    for file_path in source_audit.get("checked_files", []):
        lines.append(f"- {file_path}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(
    path: Path,
    *,
    stamp: str,
    repo_under_test: Path,
    mordor_repo: Path,
    base_url: str,
    source_audit: dict[str, Any],
    environment: dict[str, Any],
    results: list[RunResult],
    command: list[str],
) -> None:
    lines = [
        "# Mordor Representative QA Report",
        "",
        f"- Timestamp: `{stamp}`",
        f"- Repo under test: `{repo_under_test}`",
        f"- Mordor repo: `{mordor_repo}`",
        f"- Jupyter base URL: `{base_url}`",
        f"- Command: `{' '.join(command)}`",
        "",
        "## Gate Summary",
        "",
        f"- Source invariant audit: {'PASS' if source_audit.get('ok') else 'FAIL'}",
        f"- Environment/server health: {'PASS' if environment.get('ok') else 'FAIL'}",
        "",
        "## Matrix",
        "",
        "| Scenario | Backend | Result | Generated | Code Outputs | Charts | Errors | Failure |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in results:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.scenario,
                    row.backend,
                    "PASS" if row.ok else "FAIL",
                    str(row.generated_cell_count),
                    str(row.code_output_count),
                    str(row.chart_output_count),
                    str(row.error_output_count),
                    row.failure_reason.replace("|", "\\|")[:500],
                ]
            )
            + " |"
        )
    lines.extend(["", "## Artifacts", ""])
    for row in results:
        lines.extend(
            [
                f"### {row.scenario} / {row.backend}",
                "",
                f"- Start notebook: `{row.start_notebook}`",
                f"- Final notebook: `{row.final_notebook}`",
                f"- Screenshot: `{row.screenshot}`",
                f"- Manifest: `{row.manifest_path}`",
                f"- Transcripts: {', '.join(f'`{p}`' for p in row.transcript_paths) if row.transcript_paths else 'none'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Source Invariant Findings",
            "",
            "No findings." if source_audit.get("ok") else json.dumps(source_audit.get("findings"), indent=2),
            "",
            "## Environment",
            "",
            "```json",
            json.dumps(environment, indent=2, sort_keys=True, default=str),
            "```",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Mordor Notebook representative Codex/Cursor QA matrix.")
    default_repo = os.environ.get("MORDOR_REPO") or os.environ.get("MORDOR_DEFAULT_REPO")
    parser.add_argument("--repo", type=Path, default=Path(default_repo) if default_repo else None)
    parser.add_argument("--base-url", default="http://127.0.0.1:5011")
    parser.add_argument("--jupyter-prefix", default="/jlab")
    parser.add_argument("--artifact-dir", type=Path)
    parser.add_argument("--scenario", action="append", help="Scenario id or comma-separated ids. Defaults to all eight.")
    parser.add_argument("--backend", action="append", help="Backend or comma-separated backends: codex,cursor. Defaults to both.")
    parser.add_argument("--agent-timeout-ms", type=int, default=15 * 60 * 1000)
    parser.add_argument("--agent-stall-ms", type=int, default=120 * 1000)
    parser.add_argument("--skip-runs", action="store_true", help="Only write gate artifacts and starter notebooks.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.repo is None:
        raise SystemExit("--repo or MORDOR_REPO is required")
    repo_under_test = args.repo.expanduser().resolve()
    mordor_repo = Path(__file__).resolve().parents[1]
    jupyter_prefix = "/" + args.jupyter_prefix.strip("/")
    stamp = utc_stamp()
    artifact_dir = (
        args.artifact_dir
        or repo_under_test / "milestones" / "mordor_representative_qa" / stamp
    ).expanduser().resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)
    work_notebook_dir = repo_under_test / "notebooks" / "qa_scratch" / "mordor_representative_qa" / stamp
    work_notebook_dir.mkdir(parents=True, exist_ok=True)

    scenarios = select_scenarios(args.scenario)
    backends = select_backends(args.backend)
    source_audit = audit_source_invariants(mordor_repo, repo_under_test)
    environment = environment_audit(
        mordor_repo=mordor_repo,
        repo_under_test=repo_under_test,
        base_url=args.base_url,
        jupyter_prefix=jupyter_prefix,
    )
    write_source_grep(artifact_dir / "source_grep.txt", source_audit)

    results: list[RunResult] = []
    if not source_audit.get("ok"):
        print(json.dumps({"ok": False, "error": "source invariant audit failed", "artifact_dir": str(artifact_dir)}, indent=2))
    elif not environment.get("ok"):
        print(json.dumps({"ok": False, "error": "environment audit failed", "artifact_dir": str(artifact_dir)}, indent=2))
    elif args.skip_runs:
        for scenario in scenarios:
            for backend in backends:
                notebook_path = create_starter_notebook(repo_under_test, work_notebook_dir, scenario, backend, stamp)
                dest = artifact_dir / "notebooks" / f"{scenario.sid}_{backend}_start.ipynb"
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(notebook_path, dest)
    else:
        with sync_playwright() as playwright:
            for backend in backends:
                for scenario in scenarios:
                    print(f"[{datetime.now(timezone.utc).isoformat()}] running {backend} / {scenario.sid}", flush=True)
                    result = run_one_case(
                        playwright=playwright,
                        scenario=scenario,
                        backend=backend,
                        stamp=stamp,
                        repo_under_test=repo_under_test,
                        base_url=args.base_url,
                        jupyter_prefix=jupyter_prefix,
                        work_notebook_dir=work_notebook_dir,
                        artifact_dir=artifact_dir,
                        agent_timeout_ms=args.agent_timeout_ms,
                        agent_stall_ms=args.agent_stall_ms,
                    )
                    results.append(result)
                    print(json.dumps(asdict(result), indent=2, sort_keys=True, default=str), flush=True)

    summary_ok = bool(
        source_audit.get("ok")
        and environment.get("ok")
        and ((args.skip_runs and not results) or (results and all(row.ok for row in results)))
    )
    summary = {
        "ok": summary_ok,
        "timestamp": stamp,
        "repo_root": str(repo_under_test),
        "mordor_repo": str(mordor_repo),
        "base_url": args.base_url,
        "jupyter_prefix": jupyter_prefix,
        "artifact_dir": str(artifact_dir),
        "source_audit": source_audit,
        "environment": environment,
        "selected_scenarios": [scenario.sid for scenario in scenarios],
        "selected_backends": backends,
        "results": [asdict(row) for row in results],
    }
    write_json(artifact_dir / "summary.json", summary)
    write_report(
        artifact_dir / "report.md",
        stamp=stamp,
        repo_under_test=repo_under_test,
        mordor_repo=mordor_repo,
        base_url=args.base_url,
        source_audit=source_audit,
        environment=environment,
        results=results,
        command=sys.argv,
    )
    print(json.dumps({"ok": summary["ok"], "artifact_dir": str(artifact_dir), "runs": len(results)}, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
