import json

from mordornotebook.notebook_document import insert_cell_into_notebook_file


def test_insert_cell_into_notebook_file_appends_code_cell(tmp_path):
    notebook = tmp_path / "qa.ipynb"
    notebook.write_text(
        json.dumps(
            {
                "cells": [{"cell_type": "markdown", "metadata": {}, "source": ["# QA\n"]}],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
        ),
        encoding="utf-8",
    )

    result = insert_cell_into_notebook_file(
        notebook,
        cell_type="code",
        source="# Mordor generated: panel load\n1 + 1",
        operation_id="op-1",
        session_id="session-1",
    )

    saved = json.loads(notebook.read_text(encoding="utf-8"))
    assert result["ok"] is True
    assert result["inserted_index"] == 1
    assert len(saved["cells"]) == 2
    inserted = saved["cells"][1]
    assert inserted["cell_type"] == "code"
    assert inserted["execution_count"] is None
    assert inserted["outputs"] == []
    assert "".join(inserted["source"]).startswith("# Mordor generated: panel load")
    assert inserted["metadata"]["mordor"]["operation_id"] == "op-1"


def test_insert_cell_into_notebook_file_appends_markdown_cell(tmp_path):
    notebook = tmp_path / "qa.ipynb"
    notebook.write_text(json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}), encoding="utf-8")

    result = insert_cell_into_notebook_file(
        notebook,
        cell_type="markdown",
        source="## Mordor generated: audit",
        operation_id="op-2",
        session_id="session-2",
    )

    saved = json.loads(notebook.read_text(encoding="utf-8"))
    assert result["cell_count"] == 1
    assert saved["cells"][0]["cell_type"] == "markdown"
    assert "".join(saved["cells"][0]["source"]) == "## Mordor generated: audit"
