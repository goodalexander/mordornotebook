"""Durable notebook operation queue."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid
from typing import Any

from mordornotebook import paths


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class CellOperation:
    id: str
    op_type: str
    cell_type: str
    source: str
    after: str = "selected"
    notebook_path: str | None = None
    session_id: str | None = None
    status: str = "queued"
    created_at: str = ""
    updated_at: str = ""
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CellOperationStore:
    def __init__(self, root: Path | None = None):
        paths.ensure_base_dirs()
        self.root = root or paths.notebook_ops_dir()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, op_id: str) -> Path:
        return self.root / f"{op_id}.json"

    def create(
        self,
        cell_type: str,
        source: str,
        after: str = "selected",
        notebook_path: str | None = None,
        session_id: str | None = None,
        status: str = "queued",
        error: str | None = None,
    ) -> CellOperation:
        now = utc_now()
        op = CellOperation(
            id=str(uuid.uuid4()),
            op_type="insert_cell",
            cell_type=cell_type,
            source=source,
            after=after,
            notebook_path=notebook_path,
            session_id=session_id,
            status=status,
            created_at=now,
            updated_at=now,
            error=error,
        )
        self.save(op)
        return op

    def save(self, op: CellOperation) -> None:
        self._path(op.id).write_text(json.dumps(op.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def get(self, op_id: str) -> CellOperation:
        raw = json.loads(self._path(op_id).read_text(encoding="utf-8"))
        return CellOperation(**raw)

    def list(self, status: str | None = None, session_id: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if status and row.get("status") != status:
                continue
            if session_id and row.get("session_id") != session_id:
                continue
            rows.append(row)
            if limit and len(rows) >= limit:
                break
        return rows

    def ack(self, op_id: str, status: str = "applied", error: str | None = None) -> CellOperation:
        op = self.get(op_id)
        op.status = status
        op.error = error
        op.updated_at = utc_now()
        self.save(op)
        return op
