"""`.mordorignore` support for bounded repo context collection."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

DEFAULT_IGNORE = [
    ".git/",
    "__pycache__/",
    "*.pyc",
    ".ipynb_checkpoints/",
    ".env",
    ".venv/",
    "venv/",
    "dist/",
    "build/",
    "*.egg-info/",
    "*.parquet",
    "*.csv",
    "*.sqlite",
    "*.db",
    "secrets.*",
    "*secret*",
    "*token*",
    "*key*",
]


def load_ignore_patterns(repo: Path | str | None) -> list[str]:
    patterns = list(DEFAULT_IGNORE)
    if not repo:
        return patterns
    path = Path(repo).expanduser()
    ignore_path = path / ".mordorignore"
    if ignore_path.exists():
        for line in ignore_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                patterns.append(stripped)
    return patterns


def is_ignored(path: Path, repo: Path, patterns: list[str] | None = None) -> bool:
    patterns = patterns or load_ignore_patterns(repo)
    rel = path.relative_to(repo).as_posix()
    rel_dir = f"{rel}/" if path.is_dir() else rel
    for pattern in patterns:
        normalized = pattern.strip()
        if not normalized:
            continue
        if normalized.endswith("/") and (rel_dir.startswith(normalized) or f"/{normalized}" in rel_dir):
            return True
        if fnmatch(rel, normalized) or fnmatch(path.name, normalized):
            return True
    return False
