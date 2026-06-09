"""Command line bridge used by Codex inside tmux."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys
from typing import Any

from mordornotebook import paths
from mordornotebook.agent.factory import build_agent
from mordornotebook.context import build_context_packet, load_active_session_metadata
from mordornotebook.doctor import run_doctor
from mordornotebook.helpers import ensure_helper_workspace, helper_workspace_status
from mordornotebook.http_client import BridgeUnavailable, request_json
from mordornotebook.ops import CellOperationStore
from mordornotebook.repo import repo_diff, repo_status
from mordornotebook.visual import event_window_code, multiindex_slice_code, pnl_code


def _print(payload: Any, as_json: bool = False) -> None:
    if as_json or isinstance(payload, (dict, list)):
        print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    else:
        print(payload)


def _active_bridge_url() -> str | None:
    return load_active_session_metadata().get("bridge_url")


def _bridge(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    url = _active_bridge_url()
    if not url:
        raise BridgeUnavailable("No active Mordor runtime bridge. Call attach(...) inside a notebook first.")
    return request_json(url, method, path, payload)


def _source_from_args(args: argparse.Namespace) -> str:
    if getattr(args, "file", None):
        return Path(args.file).read_text(encoding="utf-8")
    return args.text or ""


def cmd_doctor(args: argparse.Namespace) -> int:
    result = run_doctor()
    _print(result, as_json=args.json)
    return 0 if result["ok"] else 1


def cmd_notebook_context(args: argparse.Namespace) -> int:
    try:
        payload = _bridge("GET", "/context")
    except BridgeUnavailable:
        payload = build_context_packet(metadata=load_active_session_metadata())
    _print(payload, as_json=args.json)
    return 0


def cmd_memory_list(args: argparse.Namespace) -> int:
    payload = _bridge("GET", "/memory")
    _print(payload, as_json=args.json)
    return 0


def cmd_memory_inspect(args: argparse.Namespace) -> int:
    payload = _bridge("GET", f"/memory/{args.name}?head={args.head}")
    _print(payload, as_json=args.json)
    return 0


def _insert_cell(cell_type: str, source: str, after: str = "selected") -> dict[str, Any]:
    metadata = load_active_session_metadata()
    try:
        return _bridge("POST", "/cell", {"cell_type": cell_type, "source": source, "after": after})
    except BridgeUnavailable as exc:
        op = CellOperationStore().create(
            cell_type=cell_type,
            source=source,
            after=after,
            notebook_path=metadata.get("notebook_path"),
            session_id=metadata.get("session_id"),
            status="queued",
            error=str(exc),
        )
        return {"ok": False, "queued": True, "operation": op.to_dict(), "warning": str(exc)}


def cmd_cell_insert(args: argparse.Namespace) -> int:
    payload = _insert_cell(args.type, _source_from_args(args), args.after)
    _print(payload, as_json=args.json)
    operation = payload.get("operation", {}) if isinstance(payload, dict) else {}
    queued = payload.get("queued") or operation.get("status") == "queued"
    return 0 if payload.get("ok") or queued else 1


def cmd_cells_list(args: argparse.Namespace) -> int:
    metadata = load_active_session_metadata()
    rows = CellOperationStore().list(status=args.status, session_id=args.session_id or metadata.get("session_id"), limit=args.limit)
    _print({"operations": rows}, as_json=args.json)
    return 0


def cmd_ops_ack(args: argparse.Namespace) -> int:
    op = CellOperationStore().ack(args.id, status=args.status, error=args.error)
    _print({"ok": True, "operation": op.to_dict()}, as_json=args.json)
    return 0


def cmd_memory_slice(args: argparse.Namespace) -> int:
    code = multiindex_slice_code(args.name, date=args.date, ticker=args.ticker)
    payload = _insert_cell("code", code, after=args.after)
    _print(payload if not args.print_code else code, as_json=args.json and not args.print_code)
    return 0


def cmd_visual_pnl(args: argparse.Namespace) -> int:
    code = pnl_code(args.object or args.series, column=args.column)
    payload = _insert_cell("code", code, after=args.after)
    _print(payload if not args.print_code else code, as_json=args.json and not args.print_code)
    return 0


def cmd_visual_event_window(args: argparse.Namespace) -> int:
    code = event_window_code(args.object, date=args.date, before=args.before, after=args.window_after, ticker=args.ticker)
    payload = _insert_cell("code", code, after=args.after)
    _print(payload if not args.print_code else code, as_json=args.json and not args.print_code)
    return 0


def cmd_repo_status(args: argparse.Namespace) -> int:
    repo = args.repo or load_active_session_metadata().get("repo") or Path.cwd()
    _print(repo_status(repo), as_json=args.json)
    return 0


def cmd_repo_diff(args: argparse.Namespace) -> int:
    repo = args.repo or load_active_session_metadata().get("repo") or Path.cwd()
    _print(repo_diff(repo, max_chars=args.max_chars), as_json=args.json)
    return 0


def _repo_from_args(args: argparse.Namespace) -> str | Path:
    return args.repo or load_active_session_metadata().get("repo") or Path.cwd()


def cmd_helpers_ensure(args: argparse.Namespace) -> int:
    payload = ensure_helper_workspace(_repo_from_args(args), update_root_gitignore=not args.no_root_gitignore)
    _print(payload, as_json=args.json)
    return 0 if payload.get("ok") else 1


def cmd_helpers_list(args: argparse.Namespace) -> int:
    status = helper_workspace_status(_repo_from_args(args))
    payload = {
        "ok": bool(status.get("available")),
        "repo": status.get("repo"),
        "registry_path": status.get("registry_path"),
        "rules_path": status.get("rules_path"),
        "helper_package_dir": status.get("helper_package_dir"),
        "helpers": (status.get("registry") or {}).get("helpers", []),
        "error": status.get("error"),
    }
    _print(payload, as_json=args.json)
    return 0 if payload["ok"] else 1


def _agent(args: argparse.Namespace):
    repo = _repo_from_args(args)
    ensure_helper_workspace(repo)
    return build_agent(
        backend=getattr(args, "backend", None),
        repo=repo,
        session_name=getattr(args, "session", None),
        payload={
            "codex_command": getattr(args, "codex_command", None),
            "cursor_command": getattr(args, "cursor_command", None),
            "cursor_model": getattr(args, "cursor_model", None),
            "cursor_sandbox": getattr(args, "cursor_sandbox", None),
            "cursor_force": getattr(args, "cursor_force", None),
        },
    )


def cmd_agent_start(args: argparse.Namespace) -> int:
    _print(_agent(args).start(), as_json=args.json)
    return 0


def cmd_agent_send(args: argparse.Namespace) -> int:
    prompt = _source_from_args(args)
    _print(_agent(args).send(prompt), as_json=args.json)
    return 0


def cmd_agent_capture(args: argparse.Namespace) -> int:
    _print(_agent(args).capture(lines=args.lines), as_json=args.json)
    return 0


def cmd_agent_stop(args: argparse.Namespace) -> int:
    _print(_agent(args).stop(), as_json=args.json)
    return 0


def cmd_sessions_list(args: argparse.Namespace) -> int:
    paths.ensure_base_dirs()
    rows = []
    for path in sorted(paths.sessions_dir().glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rows.append(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    _print({"sessions": rows[: args.limit]}, as_json=args.json)
    return 0


def cmd_sessions_cleanup(args: argparse.Namespace) -> int:
    # Conservative cleanup: only removes stale metadata files, not tmux sessions.
    paths.ensure_base_dirs()
    cutoff = datetime.now().timestamp() - _parse_age_seconds(args.older_than)
    removed = 0
    for path in paths.sessions_dir().glob("*.json"):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    _print({"ok": True, "removed": removed}, as_json=args.json)
    return 0


def cmd_jupyter_enable(args: argparse.Namespace) -> int:
    if args.sys_prefix:
        root = Path(sys.prefix) / "etc" / "jupyter"
    else:
        try:
            from jupyter_core.paths import jupyter_config_dir

            root = Path(jupyter_config_dir())
        except Exception:
            root = Path.home() / ".jupyter"
    config_dir = root / "jupyter_server_config.d"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "mordornotebook.json"
    payload = {"ServerApp": {"jpserver_extensions": {"mordornotebook": True}}}
    config_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print({"ok": True, "path": str(config_path), "extension": "mordornotebook"}, as_json=args.json)
    return 0


def cmd_jupyter_status(args: argparse.Namespace) -> int:
    candidates: list[Path] = []
    candidates.append(Path(sys.prefix) / "etc" / "jupyter" / "jupyter_server_config.d" / "mordornotebook.json")
    try:
        from jupyter_core.paths import jupyter_config_dir

        candidates.append(Path(jupyter_config_dir()) / "jupyter_server_config.d" / "mordornotebook.json")
    except Exception:
        pass
    rows = []
    for path in candidates:
        rows.append({"path": str(path), "exists": path.exists()})
    _print({"configs": rows}, as_json=args.json)
    return 0


def _parse_age_seconds(value: str) -> float:
    units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
    value = value.strip().lower()
    if value[-1:] in units:
        return float(value[:-1]) * units[value[-1]]
    return float(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mordorctl")
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor")
    doctor.add_argument("--json", action="store_true")
    doctor.set_defaults(func=cmd_doctor)

    notebook = sub.add_parser("notebook")
    notebook_sub = notebook.add_subparsers(dest="notebook_command", required=True)
    context = notebook_sub.add_parser("context")
    context.add_argument("--json", action="store_true")
    context.set_defaults(func=cmd_notebook_context)

    cells = sub.add_parser("cells")
    cells_sub = cells.add_subparsers(dest="cells_command", required=True)
    cells_list = cells_sub.add_parser("list")
    cells_list.add_argument("--json", action="store_true")
    cells_list.add_argument("--status")
    cells_list.add_argument("--session-id")
    cells_list.add_argument("--limit", type=int, default=50)
    cells_list.set_defaults(func=cmd_cells_list)

    cell = sub.add_parser("cell")
    cell_sub = cell.add_subparsers(dest="cell_command", required=True)
    insert = cell_sub.add_parser("insert")
    insert.add_argument("--type", choices=["code", "markdown"], default="code")
    insert.add_argument("--after", default="selected")
    insert.add_argument("--text")
    insert.add_argument("--file")
    insert.add_argument("--json", action="store_true")
    insert.set_defaults(func=cmd_cell_insert)

    ops = sub.add_parser("ops")
    ops_sub = ops.add_subparsers(dest="ops_command", required=True)
    ack = ops_sub.add_parser("ack")
    ack.add_argument("id")
    ack.add_argument("--status", default="applied")
    ack.add_argument("--error")
    ack.add_argument("--json", action="store_true")
    ack.set_defaults(func=cmd_ops_ack)

    memory = sub.add_parser("memory")
    memory_sub = memory.add_subparsers(dest="memory_command", required=True)
    memory_list = memory_sub.add_parser("list")
    memory_list.add_argument("--json", action="store_true")
    memory_list.set_defaults(func=cmd_memory_list)
    inspect = memory_sub.add_parser("inspect")
    inspect.add_argument("name")
    inspect.add_argument("--head", type=int, default=20)
    inspect.add_argument("--json", action="store_true")
    inspect.set_defaults(func=cmd_memory_inspect)
    slice_cmd = memory_sub.add_parser("slice")
    slice_cmd.add_argument("name")
    slice_cmd.add_argument("--date")
    slice_cmd.add_argument("--ticker")
    slice_cmd.add_argument("--after", default="selected")
    slice_cmd.add_argument("--print-code", action="store_true")
    slice_cmd.add_argument("--json", action="store_true")
    slice_cmd.set_defaults(func=cmd_memory_slice)

    visual = sub.add_parser("visual")
    visual_sub = visual.add_subparsers(dest="visual_command", required=True)
    pnl = visual_sub.add_parser("pnl")
    pnl.add_argument("--object")
    pnl.add_argument("--series")
    pnl.add_argument("--column")
    pnl.add_argument("--after", default="selected")
    pnl.add_argument("--print-code", action="store_true")
    pnl.add_argument("--json", action="store_true")
    pnl.set_defaults(func=cmd_visual_pnl)
    event = visual_sub.add_parser("event-window")
    event.add_argument("--object", required=True)
    event.add_argument("--date", required=True)
    event.add_argument("--ticker")
    event.add_argument("--before", type=int, default=5)
    event.add_argument("--window-after", type=int, default=5)
    event.add_argument("--after", default="selected")
    event.add_argument("--print-code", action="store_true")
    event.add_argument("--json", action="store_true")
    event.set_defaults(func=cmd_visual_event_window)

    repo = sub.add_parser("repo")
    repo_sub = repo.add_subparsers(dest="repo_command", required=True)
    status = repo_sub.add_parser("status")
    status.add_argument("--repo")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=cmd_repo_status)
    diff = repo_sub.add_parser("diff")
    diff.add_argument("--repo")
    diff.add_argument("--max-chars", type=int, default=120_000)
    diff.add_argument("--json", action="store_true")
    diff.set_defaults(func=cmd_repo_diff)

    helpers = sub.add_parser("helpers")
    helpers_sub = helpers.add_subparsers(dest="helpers_command", required=True)
    helpers_ensure = helpers_sub.add_parser("ensure")
    helpers_ensure.add_argument("--repo")
    helpers_ensure.add_argument("--no-root-gitignore", action="store_true")
    helpers_ensure.add_argument("--json", action="store_true")
    helpers_ensure.set_defaults(func=cmd_helpers_ensure)
    helpers_list = helpers_sub.add_parser("list")
    helpers_list.add_argument("--repo")
    helpers_list.add_argument("--json", action="store_true")
    helpers_list.set_defaults(func=cmd_helpers_list)

    agent = sub.add_parser("agent")
    agent_sub = agent.add_subparsers(dest="agent_command", required=True)
    start = agent_sub.add_parser("start")
    start.add_argument("--repo")
    start.add_argument("--session")
    start.add_argument("--backend", choices=["codex", "cursor"])
    start.add_argument("--codex-command")
    start.add_argument("--cursor-command")
    start.add_argument("--cursor-model")
    start.add_argument("--cursor-sandbox", choices=["enabled", "disabled"])
    start.add_argument("--cursor-force", action="store_true", default=None)
    start.add_argument("--json", action="store_true")
    start.set_defaults(func=cmd_agent_start)
    send = agent_sub.add_parser("send")
    send.add_argument("--repo")
    send.add_argument("--session")
    send.add_argument("--backend", choices=["codex", "cursor"])
    send.add_argument("--codex-command")
    send.add_argument("--cursor-command")
    send.add_argument("--cursor-model")
    send.add_argument("--cursor-sandbox", choices=["enabled", "disabled"])
    send.add_argument("--cursor-force", action="store_true", default=None)
    send.add_argument("--text")
    send.add_argument("--file")
    send.add_argument("--json", action="store_true")
    send.set_defaults(func=cmd_agent_send)
    capture = agent_sub.add_parser("capture")
    capture.add_argument("--repo")
    capture.add_argument("--session")
    capture.add_argument("--backend", choices=["codex", "cursor"])
    capture.add_argument("--codex-command")
    capture.add_argument("--cursor-command")
    capture.add_argument("--cursor-model")
    capture.add_argument("--cursor-sandbox", choices=["enabled", "disabled"])
    capture.add_argument("--cursor-force", action="store_true", default=None)
    capture.add_argument("--lines", type=int, default=200)
    capture.add_argument("--json", action="store_true")
    capture.set_defaults(func=cmd_agent_capture)
    stop = agent_sub.add_parser("stop")
    stop.add_argument("--repo")
    stop.add_argument("--session")
    stop.add_argument("--backend", choices=["codex", "cursor"])
    stop.add_argument("--codex-command")
    stop.add_argument("--cursor-command")
    stop.add_argument("--cursor-model")
    stop.add_argument("--cursor-sandbox", choices=["enabled", "disabled"])
    stop.add_argument("--cursor-force", action="store_true", default=None)
    stop.add_argument("--json", action="store_true")
    stop.set_defaults(func=cmd_agent_stop)

    sessions = sub.add_parser("sessions")
    sessions_sub = sessions.add_subparsers(dest="sessions_command", required=True)
    sessions_list = sessions_sub.add_parser("list")
    sessions_list.add_argument("--limit", type=int, default=50)
    sessions_list.add_argument("--json", action="store_true")
    sessions_list.set_defaults(func=cmd_sessions_list)
    sessions_cleanup = sessions_sub.add_parser("cleanup")
    sessions_cleanup.add_argument("--older-than", default="7d")
    sessions_cleanup.add_argument("--json", action="store_true")
    sessions_cleanup.set_defaults(func=cmd_sessions_cleanup)

    jupyter = sub.add_parser("jupyter")
    jupyter_sub = jupyter.add_subparsers(dest="jupyter_command", required=True)
    jupyter_enable = jupyter_sub.add_parser("enable")
    jupyter_enable.add_argument("--sys-prefix", action="store_true")
    jupyter_enable.add_argument("--json", action="store_true")
    jupyter_enable.set_defaults(func=cmd_jupyter_enable)
    jupyter_status = jupyter_sub.add_parser("status")
    jupyter_status.add_argument("--json", action="store_true")
    jupyter_status.set_defaults(func=cmd_jupyter_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except BridgeUnavailable as exc:
        print(f"mordorctl: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
