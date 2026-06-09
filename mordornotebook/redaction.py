"""Redaction helpers for prompts, logs, context packets, and doctor output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


SECRET_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("openai_key", re.compile(r"sk-[A-Za-z0-9_\-]{20,}")),
    ("generic_api_key_assignment", re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*=\s*['\"][^'\"]+['\"]")),
    ("bearer_token", re.compile(r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}")),
]


@dataclass
class RedactionFinding:
    label: str
    count: int


def redact_text(text: object, replacement: str = "[REDACTED]") -> str:
    rendered = "" if text is None else str(text)
    for _, pattern in SECRET_PATTERNS:
        rendered = pattern.sub(replacement, rendered)
    return rendered


def redaction_report(text: object) -> list[dict[str, object]]:
    rendered = "" if text is None else str(text)
    findings: list[dict[str, object]] = []
    for label, pattern in SECRET_PATTERNS:
        count = len(pattern.findall(rendered))
        if count:
            findings.append({"label": label, "count": count})
    return findings


def scan_file_for_secret_markers(path: Path) -> list[dict[str, object]]:
    if not path.exists() or not path.is_file():
        return []
    findings: list[dict[str, object]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        labels = [label for label, pattern in SECRET_PATTERNS if pattern.search(line)]
        if labels:
            findings.append(
                {
                    "path": str(path),
                    "line": line_number,
                    "labels": labels,
                    "redacted": True,
                }
            )
    return findings
