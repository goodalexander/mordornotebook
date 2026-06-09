import json

from mordornotebook.http_client import request_json
from mordornotebook.context import load_active_session_metadata, update_browser_session_metadata
from mordornotebook.runtime import attach


def _make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    return repo


def test_attach_starts_bridge_and_exposes_memory(tmp_path):
    session = attach(repo=_make_repo(tmp_path), goal="test")
    try:
        session.register("thing", {"a": 1})
        health = request_json(session.bridge_url, "GET", "/health")
        memory = request_json(session.bridge_url, "GET", "/memory")
        assert health["ok"] is True
        assert memory["objects"][0]["name"] == "thing"
    finally:
        session.stop_bridge()


def test_runtime_cell_insert_persists_to_attached_notebook(tmp_path):
    repo = _make_repo(tmp_path)
    notebook = tmp_path / "qa.ipynb"
    notebook.write_text(
        json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}),
        encoding="utf-8",
    )
    session = attach(repo=repo, goal="test", notebook_path=notebook)
    try:
        payload = request_json(
            session.bridge_url,
            "POST",
            "/cell",
            {"cell_type": "code", "source": "# Mordor generated: test\n2 + 2"},
        )
        saved = json.loads(notebook.read_text(encoding="utf-8"))
        assert payload["ok"] is True
        assert payload["persisted_notebook"] is True
        assert payload["notebook_insert"]["inserted_index"] == 0
        assert "".join(saved["cells"][0]["source"]).startswith("# Mordor generated: test")
    finally:
        session.stop_bridge()


def test_runtime_metadata_preserves_browser_notebook_binding_after_memory_register(tmp_path):
    session = attach(repo=_make_repo(tmp_path), goal="test", notebook_path=tmp_path / "runtime.ipynb")
    try:
        update_browser_session_metadata(
            {
                "notebook_path": "browser.ipynb",
                "notebook_url": "/jlab/lab/tree/browser.ipynb",
                "kernel_id": "kernel-1",
                "kernel_name": "python3",
                "session_id": "jupyter-session-1",
                "cell_count": 3,
                "active_cell_index": 2,
                "dirty": False,
            }
        )
        session.register("thing", {"a": 1})

        metadata = load_active_session_metadata()
        assert metadata["browser_notebook_path"] == "browser.ipynb"
        assert metadata["browser_session"]["kernel_id"] == "kernel-1"
        assert metadata["memory_names"] == ["thing"]
    finally:
        session.stop_bridge()


def test_runtime_cell_insert_queues_for_live_browser_when_browser_notebook_is_bound(tmp_path):
    repo = _make_repo(tmp_path)
    notebook = tmp_path / "browser_bound.ipynb"
    notebook.write_text(
        json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}),
        encoding="utf-8",
    )
    session = attach(repo=repo, goal="test", notebook_path=notebook)
    try:
        update_browser_session_metadata(
            {
                "notebook_path": "browser_bound.ipynb",
                "notebook_url": "/jlab/lab/tree/browser_bound.ipynb",
                "kernel_id": "kernel-1",
                "kernel_name": "python3",
                "session_id": "jupyter-session-1",
                "cell_count": 0,
                "active_cell_index": 0,
                "dirty": False,
            }
        )
        payload = request_json(
            session.bridge_url,
            "POST",
            "/cell",
            {"cell_type": "code", "source": "# Mordor generated: live queue\n2 + 2"},
        )
        saved = json.loads(notebook.read_text(encoding="utf-8"))

        assert payload["ok"] is True
        assert payload["queued_for_browser"] is True
        assert payload["persisted_notebook"] is False
        assert payload["operation"]["status"] == "queued"
        assert saved["cells"] == []
    finally:
        session.stop_bridge()
