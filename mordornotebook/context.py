"""Notebook, repo, memory, and operation context packets."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mordornotebook import paths
from mordornotebook.helpers import helper_workspace_status
from mordornotebook.ops import CellOperationStore
from mordornotebook.redaction import redact_text, redaction_report
from mordornotebook.repo import repo_status


def _bounded_text(value: Any, max_chars: int) -> dict[str, Any]:
    text = redact_text(value)
    return {"text": text[:max_chars], "truncated": len(text) > max_chars}


def notebook_summary(notebook_path: str | Path | None, max_output_chars: int = 4_000) -> dict[str, Any]:
    if not notebook_path:
        return {"available": False, "reason": "No notebook path configured"}
    path = Path(notebook_path).expanduser()
    if not path.exists():
        return {"available": False, "path": str(path), "reason": "Notebook path does not exist"}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"available": False, "path": str(path), "reason": str(exc)}
    cells = []
    for idx, cell in enumerate(raw.get("cells", [])):
        source = "".join(cell.get("source", ""))
        outputs = cell.get("outputs", [])
        cells.append(
            {
                "index": idx,
                "cell_type": cell.get("cell_type"),
                "source": _bounded_text(source, 8_000),
                "outputs": _bounded_text(outputs, max_output_chars),
            }
        )
    return {"available": True, "path": str(path), "cell_count": len(cells), "cells": cells}


def build_context_packet(session: Any | None = None, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    metadata = metadata or (session.metadata() if session is not None else {})
    repo = metadata.get("repo")
    memory = []
    if session is not None:
        memory = session.memory_summaries()
    ops = CellOperationStore().list(session_id=metadata.get("session_id"), limit=50)
    packet = {
        "session": metadata,
        "repo": repo_status(repo),
        "helpers": helper_workspace_status(repo),
        "notebook": notebook_summary(metadata.get("notebook_path")),
        "memory": memory,
        "operations": ops,
        "transcript_tail": read_transcript_tail(metadata, max_chars=20_000),
    }
    packet["redaction_report"] = redaction_report(json.dumps(packet, default=str))
    return packet


def read_transcript_tail(metadata: dict[str, Any], max_chars: int = 20_000) -> str:
    transcript_path = metadata.get("transcript_path")
    if not transcript_path:
        return ""
    path = Path(transcript_path)
    if not path.exists():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    return redact_text(text[-max_chars:])


def load_active_session_metadata() -> dict[str, Any]:
    path = paths.active_session_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_active_session_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    paths.ensure_base_dirs()
    paths.active_session_path().write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    session_id = metadata.get("session_id")
    if session_id:
        session_path = paths.sessions_dir() / f"{session_id}.json"
        session_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return metadata


def update_browser_session_metadata(browser_session: dict[str, Any]) -> dict[str, Any]:
    metadata = load_active_session_metadata()
    browser_clean = {
        "notebook_path": browser_session.get("notebook_path"),
        "notebook_url": browser_session.get("notebook_url"),
        "kernel_id": browser_session.get("kernel_id"),
        "kernel_name": browser_session.get("kernel_name"),
        "session_id": browser_session.get("session_id"),
        "cell_count": browser_session.get("cell_count"),
        "active_cell_index": browser_session.get("active_cell_index"),
        "dirty": browser_session.get("dirty"),
    }
    metadata["browser_session"] = browser_clean
    metadata["browser_notebook_path"] = browser_clean.get("notebook_path")
    return save_active_session_metadata(metadata)
