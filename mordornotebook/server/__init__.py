"""Minimal Jupyter Server extension for Mordor Notebook.

The kernel runtime bridge is the MVP path for live memory access. This server
extension exposes the durable operation queue and agent controls through
Jupyter's authenticated HTTP surface so a future JupyterLab panel can use the
same contracts.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import quote, urlencode

from mordornotebook.agent.factory import build_agent, normalize_backend
from pathlib import Path

from mordornotebook import paths
from mordornotebook.context import load_active_session_metadata, update_browser_session_metadata
from mordornotebook.helpers import ensure_helper_workspace
from mordornotebook.http_client import BridgeUnavailable, request_json
from mordornotebook.ops import CellOperationStore
from mordornotebook.repo import repo_status
from mordornotebook.ui import panel_markup


def _jupyter_server_extension_points() -> list[dict[str, str]]:
    return [{"module": "mordornotebook.server"}]


def _fake_transcript_path(session_name: str) -> Path:
    paths.ensure_base_dirs()
    return paths.transcripts_dir() / f"{session_name}.log"


def _request_id_from_agent_prompt(prompt: str) -> str:
    match = re.search(r"MORDOR_NOTEBOOK_DONE\s+([A-Za-z0-9_.:-]+)", prompt)
    if match:
        return match.group(1)
    match = re.search(r"Request id:\s*([A-Za-z0-9_.:-]+)", prompt)
    return match.group(1) if match else "mordor-fake-request"


def _fake_agent_send(payload: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any] | None:
    command = str(payload.get("codex_command") or "")
    if command not in {"__mordor_fake_agent__", "__mordor_fake_agent_stall__"}:
        return None

    session_name = str(payload.get("session") or payload.get("session_name") or "mordor-fake-agent")
    prompt = str(payload.get("text") or "")
    request_id = _request_id_from_agent_prompt(prompt)
    transcript_path = _fake_transcript_path(session_name)

    if command == "__mordor_fake_agent_stall__":
        transcript_path.write_text(
            "\n".join(
                [
                    "Mordor fake agent accepted request.",
                    f"Request id: {request_id}",
                    "QA mode: stalled agent. No completion marker will be emitted.",
                ]
            ),
            encoding="utf-8",
        )
        return {"ok": True, "session_name": session_name, "fake_agent": True, "mode": "stall"}

    browser_session = metadata.get("browser_session") or {}
    notebook_path = (
        browser_session.get("notebook_path")
        or metadata.get("browser_notebook_path")
        or metadata.get("notebook_path")
    )
    op = CellOperationStore().create(
        cell_type="markdown",
        source=(
            "## Mordor generated: fake agent\n\n"
            "The deterministic fake agent inserted this cell through the Mordor prompt box and live "
            "notebook operation queue."
        ),
        notebook_path=str(notebook_path) if notebook_path else None,
        session_id=str(metadata.get("session_id")) if metadata.get("session_id") else None,
        status="queued",
    )
    transcript_path.write_text(
        "\n".join(
            [
                "Mordor fake agent accepted request.",
                f"Request id: {request_id}",
                f"Queued notebook operation: {op.id}",
                f"MORDOR_NOTEBOOK_DONE {request_id}",
            ]
        ),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "backend": normalize_backend(payload.get("backend")),
        "session_name": session_name,
        "fake_agent": True,
        "mode": "complete",
        "operation": op.to_dict(),
    }


def _agent_from_payload(payload: dict[str, Any], metadata: dict[str, Any], *, session_name: str | None = None) -> Any:
    repo = payload.get("repo") or metadata.get("repo")
    if repo:
        ensure_helper_workspace(repo)
    return build_agent(
        backend=payload.get("backend"),
        repo=repo,
        session_name=session_name or payload.get("session") or payload.get("session_name"),
        payload=payload,
    )


class _PanelMarkupSession:
    def __init__(self, metadata: dict[str, Any]):
        self._metadata = metadata

    def metadata(self) -> dict[str, Any]:
        return self._metadata


def load_jupyter_server_extension(server_app: Any) -> None:
    try:
        from jupyter_server.base.handlers import APIHandler
        from jupyter_server.utils import url_path_join
        import tornado.web
    except Exception as exc:  # pragma: no cover - optional dependency boundary
        server_app.log.warning("Mordor server extension unavailable: %s", exc)
        return

    class BaseMordorHandler(APIHandler):
        @tornado.web.authenticated
        def options(self, *args: Any, **kwargs: Any) -> None:
            self.finish()

        def read_json(self) -> dict[str, Any]:
            if not self.request.body:
                return {}
            return json.loads(self.request.body.decode("utf-8"))

    class HealthHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def get(self) -> None:
            self.finish({"ok": True, "active_session": load_active_session_metadata()})

    class SessionHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def post(self) -> None:
            payload = self.read_json()
            browser_session = payload.get("browser_session") or payload
            metadata = update_browser_session_metadata(browser_session)
            self.finish({"ok": True, "active_session": metadata})

    class PanelMarkupHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def get(self) -> None:
            metadata = load_active_session_metadata()
            if not metadata.get("session_id"):
                self.set_status(409)
                self.finish({"ok": False, "error": "No active Mordor session. Attach in the active kernel first."})
                return
            self.finish({"ok": True, "html": panel_markup(_PanelMarkupSession(metadata))})

    class ContextHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def get(self) -> None:
            metadata = load_active_session_metadata()
            bridge_url = metadata.get("bridge_url")
            if not bridge_url:
                self.set_status(503)
                self.finish({"ok": False, "error": "No active Mordor runtime bridge"})
                return
            try:
                self.finish(request_json(bridge_url, "GET", "/context"))
            except BridgeUnavailable as exc:
                self.set_status(503)
                self.finish({"ok": False, "error": str(exc)})

    class OpsHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def get(self) -> None:
            self.finish({"operations": CellOperationStore().list(limit=100)})

    class OpsAckHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def post(self, op_id: str) -> None:
            payload = self.read_json()
            op = CellOperationStore().ack(
                op_id,
                status=str(payload.get("status", "applied")),
                error=payload.get("error"),
            )
            self.finish({"ok": True, "operation": op.to_dict()})

    class CellHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def post(self) -> None:
            payload = self.read_json()
            metadata = load_active_session_metadata()
            browser_path = metadata.get("browser_notebook_path")
            runtime_path = metadata.get("notebook_path")
            if browser_path and runtime_path:
                runtime_name = Path(str(runtime_path)).name
                browser_name = Path(str(browser_path)).name
                if runtime_name != browser_name:
                    self.set_status(409)
                    self.finish(
                        {
                            "ok": False,
                            "error": (
                                "Refusing file-backed cell mutation because the browser is on "
                                f"{browser_path!r}, but the runtime session points at {runtime_path!r}."
                            ),
                        }
                    )
                    return
            bridge_url = metadata.get("bridge_url")
            if not bridge_url:
                self.set_status(503)
                self.finish({"ok": False, "error": "No active Mordor runtime bridge"})
                return
            try:
                self.finish(request_json(bridge_url, "POST", "/cell", payload))
            except BridgeUnavailable as exc:
                self.set_status(503)
                self.finish({"ok": False, "error": str(exc)})

    class MemoryHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def get(self) -> None:
            metadata = load_active_session_metadata()
            bridge_url = metadata.get("bridge_url")
            if not bridge_url:
                self.set_status(503)
                self.finish({"ok": False, "error": "No active Mordor runtime bridge"})
                return
            try:
                self.finish(request_json(bridge_url, "GET", "/memory"))
            except BridgeUnavailable as exc:
                self.set_status(503)
                self.finish({"ok": False, "error": str(exc)})

    class MemoryInspectHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def post(self) -> None:
            metadata = load_active_session_metadata()
            bridge_url = metadata.get("bridge_url")
            payload = self.read_json()
            name = payload.get("name")
            head = payload.get("head", 20)
            if not bridge_url or not name:
                self.set_status(400)
                self.finish({"ok": False, "error": "bridge_url and name are required"})
                return
            try:
                query = urlencode({"head": head})
                self.finish(request_json(bridge_url, "GET", f"/memory/{quote(str(name), safe='')}?{query}"))
            except BridgeUnavailable as exc:
                self.set_status(503)
                self.finish({"ok": False, "error": str(exc)})

    class AgentStartHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def post(self) -> None:
            metadata = load_active_session_metadata()
            payload = self.read_json()
            try:
                self.finish(_agent_from_payload(payload, metadata).start())
            except ValueError as exc:
                self.set_status(400)
                self.finish({"ok": False, "error": str(exc)})

    class AgentSendHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def post(self) -> None:
            metadata = load_active_session_metadata()
            payload = self.read_json()
            fake_result = _fake_agent_send(payload, metadata)
            if fake_result is not None:
                self.finish(fake_result)
                return
            try:
                self.finish(_agent_from_payload(payload, metadata).send(str(payload.get("text", ""))))
            except ValueError as exc:
                self.set_status(400)
                self.finish({"ok": False, "error": str(exc)})

    class AgentCaptureHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def get(self) -> None:
            metadata = load_active_session_metadata()
            repo = metadata.get("repo")
            session_name = self.get_argument("session", None)
            backend = self.get_argument("backend", None)
            try:
                capture = build_agent(backend=backend, repo=repo, session_name=session_name).capture()
            except ValueError as exc:
                self.set_status(400)
                self.finish({"ok": False, "error": str(exc)})
                return
            if capture.get("ok") or not session_name:
                self.finish(capture)
                return
            transcript_path = _fake_transcript_path(str(session_name))
            if transcript_path.exists():
                self.finish(
                    {
                        "ok": True,
                        "session_name": session_name,
                        "text": transcript_path.read_text(encoding="utf-8", errors="replace"),
                        "transcript_path": str(transcript_path),
                        "fake_agent": True,
                    }
                )
                return
            self.finish(capture)

    class AgentStopHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def post(self) -> None:
            metadata = load_active_session_metadata()
            payload = self.read_json()
            session_name = payload.get("session") or payload.get("session_name")
            try:
                stopped = _agent_from_payload(payload, metadata, session_name=session_name).stop()
            except ValueError as exc:
                self.set_status(400)
                self.finish({"ok": False, "error": str(exc)})
                return
            if session_name:
                transcript_path = _fake_transcript_path(str(session_name))
                if transcript_path.exists():
                    with transcript_path.open("a", encoding="utf-8") as handle:
                        handle.write("\nMORDOR_NOTEBOOK_CANCELLED\n")
                    stopped = {**stopped, "fake_agent": True, "transcript_path": str(transcript_path)}
            self.finish(stopped)

    class RepoStatusHandler(BaseMordorHandler):
        @tornado.web.authenticated
        def get(self) -> None:
            self.finish(repo_status(load_active_session_metadata().get("repo")))

    base_url = server_app.web_app.settings.get("base_url", "/")
    handlers = [
        (url_path_join(base_url, "mordor/api/health"), HealthHandler),
        (url_path_join(base_url, "mordor/api/session"), SessionHandler),
        (url_path_join(base_url, "mordor/api/panel/markup"), PanelMarkupHandler),
        (url_path_join(base_url, "mordor/api/notebook/context"), ContextHandler),
        (url_path_join(base_url, "mordor/api/notebook/ops"), OpsHandler),
        (url_path_join(base_url, r"mordor/api/notebook/ops/(.*)/ack"), OpsAckHandler),
        (url_path_join(base_url, "mordor/api/notebook/cell"), CellHandler),
        (url_path_join(base_url, "mordor/api/memory"), MemoryHandler),
        (url_path_join(base_url, "mordor/api/memory/inspect"), MemoryInspectHandler),
        (url_path_join(base_url, "mordor/api/agent/start"), AgentStartHandler),
        (url_path_join(base_url, "mordor/api/agent/send"), AgentSendHandler),
        (url_path_join(base_url, "mordor/api/agent/capture"), AgentCaptureHandler),
        (url_path_join(base_url, "mordor/api/agent/stop"), AgentStopHandler),
        (url_path_join(base_url, "mordor/api/repo/status"), RepoStatusHandler),
    ]
    server_app.web_app.add_handlers(".*$", handlers)
    server_app.log.info("Mordor Notebook server extension loaded")
