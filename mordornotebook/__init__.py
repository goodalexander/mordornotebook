"""Mordor Notebook public API."""

from mordornotebook.runtime import MordorSession, attach, get_active_session

__all__ = ["MordorSession", "attach", "get_active_session"]

__version__ = "0.2.0"


def _jupyter_server_extension_points() -> list[dict[str, str]]:
    return [{"module": "mordornotebook.server"}]


def _jupyter_labextension_paths() -> list[dict[str, str]]:
    return [{"src": "labextension", "dest": "mordornotebook"}]
