"""Live in-kernel memory packet summaries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
import math
import sys
from typing import Any

from mordornotebook.redaction import redact_text


def jsonable(value: Any, max_str: int = 500) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return str(value)
        return redact_text(value)[:max_str] if isinstance(value, str) else value
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if isinstance(value, Mapping):
        return {str(k): jsonable(v, max_str=max_str) for k, v in list(value.items())[:50]}
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [jsonable(v, max_str=max_str) for v in list(value)[:50]]
    return redact_text(repr(value))[:max_str]


def _safe_len(obj: Any) -> int | None:
    try:
        return len(obj)
    except Exception:
        return None


def _memory_usage(obj: Any) -> int | None:
    try:
        if hasattr(obj, "memory_usage"):
            usage = obj.memory_usage(deep=True)
            if hasattr(usage, "sum"):
                return int(usage.sum())
            return int(usage)
    except Exception:
        pass
    try:
        return int(sys.getsizeof(obj))
    except Exception:
        return None


def summarize_index(index: Any, sample: int = 5) -> dict[str, Any]:
    info: dict[str, Any] = {
        "type": type(index).__name__,
        "name": jsonable(getattr(index, "name", None)),
        "length": _safe_len(index),
    }
    names = getattr(index, "names", None)
    if names is not None:
        info["names"] = jsonable(list(names))
    try:
        info["is_monotonic_increasing"] = bool(index.is_monotonic_increasing)
    except Exception:
        pass
    try:
        info["sample"] = jsonable(list(index[:sample]))
    except Exception:
        pass
    try:
        info["min"] = jsonable(index.min())
        info["max"] = jsonable(index.max())
    except Exception:
        pass
    if hasattr(index, "levels"):
        levels = []
        for i, level in enumerate(index.levels):
            levels.append(
                {
                    "position": i,
                    "name": jsonable(index.names[i] if getattr(index, "names", None) else None),
                    "length": _safe_len(level),
                    "sample": jsonable(list(level[:sample])),
                }
            )
        info["levels"] = levels
    return info


def summarize_dataframe(name: str, obj: Any, sample: int = 5) -> dict[str, Any]:
    head = obj.head(sample)
    tail = obj.tail(sample)
    return {
        "name": name,
        "kind": type(obj).__name__,
        "module": type(obj).__module__,
        "shape": list(obj.shape),
        "columns": [str(col) for col in list(obj.columns)[:100]],
        "columns_truncated": len(obj.columns) > 100,
        "dtypes": {str(k): str(v) for k, v in obj.dtypes.astype(str).to_dict().items()},
        "index": summarize_index(obj.index, sample=sample),
        "memory_bytes": _memory_usage(obj),
        "head": jsonable(head.reset_index().to_dict(orient="records")),
        "tail": jsonable(tail.reset_index().to_dict(orient="records")),
    }


def summarize_series(name: str, obj: Any, sample: int = 5) -> dict[str, Any]:
    return {
        "name": name,
        "kind": type(obj).__name__,
        "module": type(obj).__module__,
        "length": _safe_len(obj),
        "dtype": str(getattr(obj, "dtype", "")),
        "index": summarize_index(obj.index, sample=sample),
        "memory_bytes": _memory_usage(obj),
        "head": jsonable(obj.head(sample).reset_index().to_dict(orient="records")),
        "tail": jsonable(obj.tail(sample).reset_index().to_dict(orient="records")),
    }


def summarize_path(name: str, obj: Path) -> dict[str, Any]:
    exists = obj.exists()
    return {
        "name": name,
        "kind": "Path",
        "path": str(obj),
        "exists": exists,
        "is_file": obj.is_file() if exists else False,
        "is_dir": obj.is_dir() if exists else False,
        "size_bytes": obj.stat().st_size if exists and obj.is_file() else None,
    }


def summarize_object(name: str, obj: Any, sample: int = 5) -> dict[str, Any]:
    if hasattr(obj, "head") and hasattr(obj, "dtypes") and hasattr(obj, "columns"):
        return summarize_dataframe(name, obj, sample=sample)
    if hasattr(obj, "head") and hasattr(obj, "dtype") and hasattr(obj, "index"):
        return summarize_series(name, obj, sample=sample)
    if isinstance(obj, Path):
        return summarize_path(name, obj)
    return {
        "name": name,
        "kind": type(obj).__name__,
        "module": type(obj).__module__,
        "length": _safe_len(obj),
        "memory_bytes": _memory_usage(obj),
        "repr": redact_text(repr(obj))[:1_000],
    }


def inspect_object(name: str, obj: Any, sample: int = 20) -> dict[str, Any]:
    summary = summarize_object(name, obj, sample=sample)
    summary["inspection_rows"] = sample
    return summary
