"""Filesystem locations for Mordor Notebook."""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "mordornotebook"


def _path_from_env(name: str, default: Path) -> Path:
    value = os.environ.get(name)
    return Path(value).expanduser().resolve() if value else default


def config_dir() -> Path:
    return _path_from_env("MORDOR_CONFIG_DIR", Path.home() / ".config" / APP_NAME)


def state_dir() -> Path:
    return _path_from_env("MORDOR_STATE_DIR", Path.home() / ".local" / "state" / APP_NAME)


def config_path() -> Path:
    return config_dir() / "config.toml"


def secrets_path() -> Path:
    return config_dir() / "secrets.toml"


def sessions_dir() -> Path:
    return state_dir() / "sessions"


def transcripts_dir() -> Path:
    return state_dir() / "transcripts"


def notebook_ops_dir() -> Path:
    return state_dir() / "notebook_ops"


def logs_dir() -> Path:
    return state_dir() / "logs"


def active_session_path() -> Path:
    return state_dir() / "active_session.json"


def ensure_base_dirs() -> None:
    for path in [config_dir(), state_dir(), sessions_dir(), transcripts_dir(), notebook_ops_dir(), logs_dir()]:
        path.mkdir(parents=True, exist_ok=True)
