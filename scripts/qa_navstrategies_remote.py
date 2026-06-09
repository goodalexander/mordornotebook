#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mordornotebook import __version__, attach
from mordornotebook.ui import panel_markup


DEFAULT_NAV_REPO = Path(os.environ.get("NAVSTRATEGIES_REPO", "~/repos/navstrategies")).expanduser()


class DummySession:
    def metadata(self) -> dict[str, Any]:
        return {
            "session_id": "qa-session",
            "repo": str(DEFAULT_NAV_REPO),
            "bridge_url": "http://127.0.0.1:41533",
        }


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def request_json(base_url: str, path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    url = base_url.rstrip("/") + "/" + path.lstrip("/")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            raw = response.read().decode("utf-8")
            return int(response.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return int(exc.code), body


def pass_gate(gates: dict[str, dict[str, Any]], name: str, evidence: dict[str, Any] | None = None) -> None:
    gates[name] = {"status": "pass", "evidence": evidence or {}}


def fail_gate(gates: dict[str, dict[str, Any]], name: str, error: str, evidence: dict[str, Any] | None = None) -> None:
    gates[name] = {"status": "fail", "error": error, "evidence": evidence or {}}


def validate_panel_markup(gates: dict[str, dict[str, Any]]) -> None:
    markup = panel_markup(DummySession())
    bad_tokens = [
        "fetch(bridge",
        "bridge + path",
        "fetch(\"http://127.0.0.1:41533",
        "fetch('http://127.0.0.1:41533",
    ]
    failures = [token for token in bad_tokens if token in markup]
    if failures:
        fail_gate(gates, "panel_markup", "Panel HTML contains direct browser fetch to kernel bridge.", {"tokens": failures})
        return
    required = ["mordor/api/", "notebook/context", "notebook/cell", "agent/start", "credentials: 'same-origin'"]
    missing = [token for token in required if token not in markup]
    if missing:
        fail_gate(gates, "panel_markup", "Panel HTML is missing required Jupyter API routing tokens.", {"missing": missing})
        return
    pass_gate(gates, "panel_markup", {"direct_bridge_fetch": False})


def validate_hot_universe(gates: dict[str, dict[str, Any]], nav_repo: Path) -> None:
    sys.path.insert(0, str(nav_repo))
    from navstrategies.utilities.hot_universe import cache_status, config_from_args

    config = config_from_args()
    status = cache_status(config)
    evidence = {
        "fresh": bool(status.get("fresh")),
        "parquet_path": status.get("parquet_path"),
        "metadata": status.get("metadata"),
    }
    if not status.get("fresh"):
        fail_gate(gates, "hot_universe", "Hot universe cache is missing or stale; QA must not cold-scan from notebook.", evidence)
        return
    pass_gate(gates, "hot_universe", evidence)


def record_invalidated_example_notebook(gates: dict[str, dict[str, Any]], nav_repo: Path) -> None:
    try:
        import nbformat
    except Exception as exc:
        gates["invalidated_example_notebook"] = {
            "status": "skipped",
            "reason": f"nbformat unavailable: {exc}",
        }
        return

    notebook_path = nav_repo / "notebooks" / "mordor_navstrategies_example.ipynb"
    if not notebook_path.exists():
        gates["invalidated_example_notebook"] = {
            "status": "skipped",
            "reason": "Example notebook is missing.",
            "evidence": {"path": str(notebook_path)},
        }
        return
    nb = nbformat.read(notebook_path, as_version=4)
    code_cells = [cell for cell in nb.cells if cell.cell_type == "code"]
    executed = [cell for cell in code_cells if cell.get("execution_count") is not None]
    output_cells = [cell for cell in code_cells if cell.get("outputs")]
    gates["invalidated_example_notebook"] = {
        "status": "skipped",
        "reason": "Pre-authored analysis notebook is invalidated as Mordor Notebook acceptance evidence.",
        "evidence": {
            "path": str(notebook_path),
            "cell_count": len(nb.cells),
            "code_cell_count": len(code_cells),
            "executed_code_cells": len(executed),
            "output_code_cells": len(output_cells),
        },
    }


def validate_jupyter_proxy(gates: dict[str, dict[str, Any]], api_base: str, nav_repo: Path) -> None:
    status, payload = request_json(api_base, "health")
    if status != 200 or not payload.get("ok"):
        fail_gate(gates, "jupyter_extension_health", "Mordor Jupyter server extension health failed.", {"status": status, "payload": payload})
        return
    pass_gate(gates, "jupyter_extension_health", {"status": status, "active_session_keys": sorted((payload.get("active_session") or {}).keys())})

    session = attach(repo=nav_repo, goal="remote QA server proxy")
    session.register("qa_frame", pd.DataFrame({"ticker": ["AAPL", "NVDA"], "value": [1, 2]}))
    try:
        proxy_results: dict[str, Any] = {}
        for path in ["memory", "notebook/context", "repo/status"]:
            endpoint_status, endpoint_payload = request_json(api_base, path)
            proxy_results[path] = {
                "status": endpoint_status,
                "keys": sorted(endpoint_payload.keys()) if isinstance(endpoint_payload, dict) else [],
            }
            if endpoint_status != 200:
                fail_gate(gates, "jupyter_proxy", f"Proxy endpoint failed: {path}", proxy_results)
                return
        memory_status, memory_payload = request_json(api_base, "memory")
        names = [item.get("name") for item in memory_payload.get("objects", [])]
        proxy_results["memory_names"] = names
        if "qa_frame" not in names:
            fail_gate(gates, "jupyter_proxy", "Registered memory object was not visible through Jupyter proxy.", proxy_results)
            return
        pass_gate(gates, "jupyter_proxy", proxy_results)
    finally:
        session.stop_bridge()


def maybe_start_agent(gates: dict[str, dict[str, Any]], api_base: str, nav_repo: Path) -> None:
    session = attach(repo=nav_repo, goal="remote QA agent start")
    try:
        status, payload = request_json(api_base, "agent/start", method="POST", payload={})
        evidence = {"status": status, "payload": payload}
        if status != 200 or not payload.get("ok"):
            fail_gate(gates, "agent_start", "Agent start failed through Jupyter proxy.", evidence)
            return
        time.sleep(1.0)
        capture_status, capture_payload = request_json(api_base, "agent/capture")
        evidence["capture_status"] = capture_status
        evidence["capture_keys"] = sorted(capture_payload.keys()) if isinstance(capture_payload, dict) else []
        evidence["capture_ok"] = capture_payload.get("ok")
        pass_gate(gates, "agent_start", evidence)
    finally:
        session.stop_bridge()


def write_artifacts(artifact_dir: Path, summary: dict[str, Any]) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    lines = [
        "# Mordor Navstrategies Remote QA Summary",
        "",
        f"- ok: `{summary['ok']}`",
        f"- base_url: `{summary['base_url']}`",
        f"- api_base: `{summary['api_base']}`",
        f"- mordor_version: `{summary['mordor_version']}`",
        "",
        "| Gate | Status |",
        "|---|---|",
    ]
    for name, gate in summary["gates"].items():
        lines.append(f"| `{name}` | `{gate.get('status')}` |")
    lines.append("")
    (artifact_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run bounded Mordor Notebook QA against the navstrategies gateway.")
    parser.add_argument("--base-url", default="http://127.0.0.1:5011")
    parser.add_argument("--jupyter-prefix", default="/jlab")
    parser.add_argument("--nav-repo", type=Path, default=DEFAULT_NAV_REPO)
    parser.add_argument("--artifact-dir", type=Path, default=None)
    parser.add_argument("--start-agent", action="store_true", help="Also start/capture the tmux Codex agent through Jupyter.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    nav_repo = args.nav_repo.expanduser().resolve()
    artifact_dir = args.artifact_dir or nav_repo / "milestones" / "mordor_remote_qa" / utc_stamp()
    api_base = f"{args.base_url.rstrip('/')}/{args.jupyter_prefix.strip('/')}/mordor/api"
    gates: dict[str, dict[str, Any]] = {}
    summary = {
        "ok": False,
        "base_url": args.base_url,
        "api_base": api_base,
        "nav_repo": str(nav_repo),
        "artifact_dir": str(artifact_dir),
        "mordor_version": __version__,
        "gates": gates,
    }

    checks = [
        lambda: validate_panel_markup(gates),
        lambda: validate_hot_universe(gates, nav_repo),
        lambda: record_invalidated_example_notebook(gates, nav_repo),
        lambda: validate_jupyter_proxy(gates, api_base, nav_repo),
    ]
    if args.start_agent:
        checks.append(lambda: maybe_start_agent(gates, api_base, nav_repo))

    for check in checks:
        check()

    summary["ok"] = bool(gates) and all(gate.get("status") in {"pass", "skipped"} for gate in gates.values())
    write_artifacts(artifact_dir, summary)
    print(json.dumps(summary, indent=2, sort_keys=True, default=str))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
