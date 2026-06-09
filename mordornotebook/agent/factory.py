"""Agent backend selection."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mordornotebook.agent.cursor import CursorAgent
from mordornotebook.agent.tmux import TmuxAgent
from mordornotebook.config import load_config


def normalize_backend(value: object | None) -> str:
    backend = str(value or "").strip().lower()
    if not backend:
        backend = str(load_config().agent_backend or "codex").strip().lower()
    if backend not in {"codex", "cursor"}:
        raise ValueError(f"Unsupported Mordor agent backend: {backend!r}")
    return backend


def build_agent(
    *,
    backend: object | None = None,
    repo: str | Path | None = None,
    session_name: str | None = None,
    payload: dict[str, Any] | None = None,
) -> TmuxAgent | CursorAgent:
    payload = payload or {}
    selected = normalize_backend(backend if backend is not None else payload.get("backend"))
    if selected == "cursor":
        return CursorAgent(
            repo=repo,
            session_name=session_name,
            cursor_command=payload.get("cursor_command"),
            cursor_model=payload.get("cursor_model"),
            cursor_sandbox=payload.get("cursor_sandbox"),
            cursor_force=payload.get("cursor_force"),
        )
    return TmuxAgent(
        repo=repo,
        session_name=session_name,
        codex_command=payload.get("codex_command"),
    )
