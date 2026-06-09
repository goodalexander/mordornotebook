"""Runtime bridge loaded inside an active IPython/Jupyter kernel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import threading
import uuid
from typing import Any
from urllib.parse import parse_qs, urlparse

from mordornotebook import paths
from mordornotebook.config import load_config
from mordornotebook.context import build_context_packet, load_active_session_metadata
from mordornotebook.helpers import ensure_helper_workspace, helper_workspace_status
from mordornotebook.memory import inspect_object, summarize_object
from mordornotebook.notebook_document import insert_cell_into_notebook_file
from mordornotebook.ops import CellOperationStore
from mordornotebook.redaction import redact_text

_ACTIVE_SESSION: "MordorSession | None" = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_ipython_shell() -> Any | None:
    try:
        from IPython import get_ipython

        return get_ipython()
    except Exception:
        return None


def _detect_notebook_path(notebook_path: str | Path | None = None) -> str | None:
    if notebook_path:
        return str(Path(notebook_path).expanduser().resolve())
    env_path = os.environ.get("MORDOR_NOTEBOOK_PATH") or os.environ.get("JPY_SESSION_NAME")
    if env_path:
        path = Path(env_path).expanduser()
        return str(path.resolve()) if path.exists() else str(path)
    socket.gethostname()  # harmless call keeps detection local and cheap
    return None


def _browser_bound_to_session_notebook(session_id: str, notebook_path: str | None) -> bool:
    if not notebook_path:
        return False
    metadata = load_active_session_metadata()
    if metadata.get("session_id") != session_id:
        return False
    browser_path = metadata.get("browser_notebook_path")
    if not browser_path:
        return False
    return Path(str(browser_path)).name == Path(str(notebook_path)).name


@dataclass
class MordorSession:
    repo: str | None = None
    goal: str | None = None
    notebook_path: str | None = None
    helper_workspace: dict[str, Any] | None = None
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=utc_now)
    bridge_url: str | None = None
    _memory: dict[str, Any] = field(default_factory=dict, repr=False)
    _summaries: dict[str, dict[str, Any]] = field(default_factory=dict, repr=False)
    _server: ThreadingHTTPServer | None = field(default=None, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    def start_bridge(self) -> None:
        if self._server is not None:
            return
        handler = _handler_factory(self)
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self._server = server
        self.bridge_url = f"http://127.0.0.1:{server.server_port}"
        self._thread = threading.Thread(target=server.serve_forever, name=f"mordor-{self.session_id}", daemon=True)
        self._thread.start()
        self.save_metadata()

    def stop_bridge(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self.bridge_url = None
        self.save_metadata()

    def register(self, name: str, obj: Any, sample: int | None = None) -> dict[str, Any]:
        if not name or not name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Memory packet name must be alphanumeric with optional '-' or '_'")
        sample = sample or load_config().memory_sample_rows
        self._memory[name] = obj
        self._summaries[name] = summarize_object(name, obj, sample=sample)
        self.save_metadata()
        return self._summaries[name]

    def unregister(self, name: str) -> None:
        self._memory.pop(name, None)
        self._summaries.pop(name, None)
        self.save_metadata()

    def memory_summaries(self) -> list[dict[str, Any]]:
        return list(self._summaries.values())

    def inspect_memory(self, name: str, sample: int = 20) -> dict[str, Any]:
        if name not in self._memory:
            raise KeyError(f"No registered memory packet named {name!r}")
        return inspect_object(name, self._memory[name], sample=sample)

    def insert_cell(self, cell_type: str, source: str, after: str = "selected") -> dict[str, Any]:
        store = CellOperationStore()
        op = store.create(
            cell_type=cell_type,
            source=source,
            after=after,
            notebook_path=self.notebook_path,
            session_id=self.session_id,
            status="queued",
        )
        runtime_attempted = False
        runtime_error: str | None = None
        runtime_skipped_reason: str | None = None

        notebook_insert: dict[str, Any] | None = None
        notebook_error: str | None = None
        browser_bound = _browser_bound_to_session_notebook(self.session_id, self.notebook_path)
        if browser_bound:
            notebook_error = "Browser-bound session queued this cell for live JupyterLab insertion"
            runtime_skipped_reason = (
                "active browser notebook is bound to this session; skipped direct .ipynb mutation "
                "so the JupyterLab extension can insert the cell into the live document model"
            )
        elif self.notebook_path:
            try:
                notebook_insert = insert_cell_into_notebook_file(
                    self.notebook_path,
                    cell_type=cell_type,
                    source=source,
                    after=after,
                    operation_id=op.id,
                    session_id=self.session_id,
                )
            except Exception as exc:
                notebook_error = redact_text(str(exc))
        else:
            notebook_error = "No notebook_path configured on Mordor session"
            shell = _get_ipython_shell()
            if shell is not None and hasattr(shell, "set_next_input"):
                try:
                    if cell_type == "markdown":
                        payload = f"%%markdown\n{source}"
                    else:
                        payload = source
                    shell.set_next_input(payload, replace=False)
                    runtime_attempted = True
                except Exception as exc:
                    runtime_error = redact_text(str(exc))
            else:
                runtime_error = "No active IPython frontend accepted set_next_input"

        if self.notebook_path and notebook_insert:
            runtime_skipped_reason = (
                "notebook_path is configured; skipped IPython.set_next_input "
                "to avoid duplicate live/file insertions"
            )

        persisted = bool(notebook_insert and notebook_insert.get("ok"))
        if persisted:
            op = store.ack(op.id, status="persisted", error=runtime_error)
        elif browser_bound:
            op = store.ack(op.id, status="queued", error=None)
        elif runtime_attempted:
            op = store.ack(op.id, status="runtime_delivery_attempted", error=notebook_error)
        else:
            op = store.ack(op.id, status="queued", error=notebook_error or runtime_error)
        return {
            "ok": persisted or runtime_attempted or browser_bound,
            "queued_for_browser": browser_bound,
            "operation": op.to_dict(),
            "applied_live": runtime_attempted,
            "runtime_delivery": {
                "attempted": runtime_attempted,
                "optimistic_only": runtime_attempted,
                "error": runtime_error,
                "skipped_reason": runtime_skipped_reason,
            },
            "persisted_notebook": persisted,
            "notebook_insert": notebook_insert,
            "notebook_error": notebook_error,
        }

    def metadata(self) -> dict[str, Any]:
        paths.ensure_base_dirs()
        from mordornotebook.agent.tmux import TmuxAgent

        agent = TmuxAgent(repo=self.repo)
        transcript_path = paths.transcripts_dir() / f"{agent.session_name}.log"
        return {
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": utc_now(),
            "repo": self.repo,
            "goal": self.goal,
            "notebook_path": self.notebook_path,
            "bridge_url": self.bridge_url,
            "memory_names": sorted(self._memory.keys()),
            "tmux_session_name": agent.session_name,
            "transcript_path": str(transcript_path),
            "helper_workspace": self.helper_workspace or helper_workspace_status(self.repo),
        }

    def save_metadata(self) -> None:
        paths.ensure_base_dirs()
        metadata = self.metadata()
        active_path = paths.active_session_path()
        if active_path.exists():
            try:
                existing = json.loads(active_path.read_text(encoding="utf-8"))
            except Exception:
                existing = {}
            same_session = existing.get("session_id") == metadata.get("session_id")
            same_bridge = bool(existing.get("bridge_url") and existing.get("bridge_url") == metadata.get("bridge_url"))
            if same_session or same_bridge:
                for key in ("browser_session", "browser_notebook_path"):
                    if key in existing:
                        metadata[key] = existing[key]
        session_path = paths.sessions_dir() / f"{self.session_id}.json"
        session_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
        active_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")

    def panel(self) -> Any:
        from mordornotebook.ui import display_panel

        return display_panel(self)


def attach(repo: str | Path | None = None, goal: str | None = None, notebook_path: str | Path | None = None) -> MordorSession:
    """Attach Mordor Notebook to the current kernel and start the local bridge."""
    global _ACTIVE_SESSION
    config = load_config()
    resolved_repo = str(Path(repo or config.default_repo).expanduser().resolve()) if (repo or config.default_repo) else None
    helper_workspace = ensure_helper_workspace(resolved_repo) if resolved_repo else None
    session = MordorSession(
        repo=resolved_repo,
        goal=goal,
        notebook_path=_detect_notebook_path(notebook_path),
        helper_workspace=helper_workspace,
    )
    session.start_bridge()
    _ACTIVE_SESSION = session
    return session


def get_active_session() -> MordorSession | None:
    return _ACTIVE_SESSION


def _handler_factory(session: MordorSession) -> type[BaseHTTPRequestHandler]:
    class RuntimeBridgeHandler(BaseHTTPRequestHandler):
        server_version = "MordorRuntime/0.2"

        def log_message(self, fmt: str, *args: Any) -> None:
            return

        def _send(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, default=str).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802 - stdlib handler API
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                return {}
            raw = self.rfile.read(length).decode("utf-8")
            return json.loads(raw) if raw else {}

        def do_GET(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/health":
                    self._send(200, {"ok": True, "session": session.metadata()})
                elif parsed.path == "/memory":
                    self._send(200, {"objects": session.memory_summaries()})
                elif parsed.path.startswith("/memory/"):
                    name = parsed.path.split("/", 2)[2]
                    sample = int(query.get("head", ["20"])[0])
                    self._send(200, session.inspect_memory(name, sample=sample))
                elif parsed.path == "/context":
                    self._send(200, build_context_packet(session=session))
                elif parsed.path == "/ops":
                    self._send(200, {"operations": CellOperationStore().list(session_id=session.session_id)})
                elif parsed.path == "/agent/capture":
                    from mordornotebook.agent.tmux import TmuxAgent

                    self._send(200, TmuxAgent(repo=session.repo).capture())
                else:
                    self._send(404, {"ok": False, "error": "Unknown endpoint"})
            except Exception as exc:
                self._send(500, {"ok": False, "error": redact_text(str(exc))})

        def do_POST(self) -> None:  # noqa: N802 - stdlib handler API
            parsed = urlparse(self.path)
            try:
                payload = self._read_json()
                if parsed.path == "/cell":
                    result = session.insert_cell(
                        cell_type=str(payload.get("cell_type", "code")),
                        source=str(payload.get("source", "")),
                        after=str(payload.get("after", "selected")),
                    )
                    self._send(200, result)
                elif parsed.path == "/agent/start":
                    from mordornotebook.agent.tmux import TmuxAgent

                    self._send(200, TmuxAgent(repo=session.repo).start())
                elif parsed.path == "/agent/send":
                    from mordornotebook.agent.tmux import TmuxAgent

                    self._send(200, TmuxAgent(repo=session.repo).send(str(payload.get("text", ""))))
                elif parsed.path.startswith("/ops/") and parsed.path.endswith("/ack"):
                    op_id = parsed.path.split("/")[2]
                    op = CellOperationStore().ack(
                        op_id,
                        status=str(payload.get("status", "applied")),
                        error=payload.get("error"),
                    )
                    self._send(200, {"ok": True, "operation": op.to_dict()})
                else:
                    self._send(404, {"ok": False, "error": "Unknown endpoint"})
            except Exception as exc:
                self._send(500, {"ok": False, "error": redact_text(str(exc))})

    return RuntimeBridgeHandler
