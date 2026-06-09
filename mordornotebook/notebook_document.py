"""Notebook document mutation helpers."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile
from typing import Any
import uuid


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _source_lines(source: str) -> list[str]:
    if not source:
        return []
    lines = source.splitlines(keepends=True)
    if lines and not lines[-1].endswith(("\n", "\r")):
        return lines
    return lines


def _new_cell(cell_type: str, source: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    cell_metadata = dict(metadata or {})
    cell_id = uuid.uuid4().hex[:8]
    if cell_type == "markdown":
        return {"cell_type": "markdown", "id": cell_id, "metadata": cell_metadata, "source": _source_lines(source)}
    if cell_type == "code":
        return {
            "cell_type": "code",
            "id": cell_id,
            "execution_count": None,
            "metadata": cell_metadata,
            "outputs": [],
            "source": _source_lines(source),
        }
    raise ValueError(f"Unsupported cell type: {cell_type!r}")


def insert_cell_into_notebook_file(
    notebook_path: str | Path,
    *,
    cell_type: str,
    source: str,
    after: str = "end",
    operation_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Insert a cell into an ipynb file and atomically replace the file.

    The MVP uses append semantics because a server-side caller cannot know the
    current JupyterLab selection without a frontend extension handshake.
    """

    path = Path(notebook_path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    cells = raw.setdefault("cells", [])
    if not isinstance(cells, list):
        raise ValueError(f"Notebook cells field is not a list: {path}")

    metadata = {
        "mordor": {
            "operation_id": operation_id,
            "session_id": session_id,
            "inserted_at": utc_now(),
            "inserted_by": "mordorctl",
        }
    }
    cell = _new_cell(cell_type, source, metadata=metadata)
    index = len(cells)
    if after not in {"end", "selected"}:
        try:
            requested = int(after)
        except ValueError:
            requested = len(cells) - 1
        index = max(0, min(requested + 1, len(cells)))
    cells.insert(index, cell)

    raw.setdefault("nbformat", 4)
    raw.setdefault("nbformat_minor", 5)
    raw.setdefault("metadata", {})

    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=str(path.parent), delete=False) as handle:
        json.dump(raw, handle, indent=1, ensure_ascii=False)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)
    return {
        "ok": True,
        "path": str(path),
        "inserted_index": index,
        "cell_count": len(cells),
        "cell_type": cell_type,
        "after": after,
    }
