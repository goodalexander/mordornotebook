"""Repository inspection helpers."""

from __future__ import annotations

from pathlib import Path
import subprocess

from mordornotebook.redaction import redact_text


def _run_git(repo: Path, args: list[str], timeout: float = 8.0) -> dict[str, object]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": redact_text(proc.stdout),
            "stderr": redact_text(proc.stderr),
        }
    except Exception as exc:  # pragma: no cover - defensive shell boundary
        return {"ok": False, "returncode": None, "stdout": "", "stderr": str(exc)}


def repo_status(repo: str | Path | None) -> dict[str, object]:
    if not repo:
        return {"ok": False, "error": "No repo configured"}
    path = Path(repo).expanduser().resolve()
    if not path.exists():
        return {"ok": False, "repo": str(path), "error": "Repo path does not exist"}
    branch = _run_git(path, ["branch", "--show-current"])
    status = _run_git(path, ["status", "--short"])
    untracked = [line for line in str(status.get("stdout", "")).splitlines() if line.startswith("??")]
    return {
        "ok": bool(branch["ok"] and status["ok"]),
        "repo": str(path),
        "branch": str(branch.get("stdout", "")).strip(),
        "dirty": bool(str(status.get("stdout", "")).strip()),
        "untracked_count": len(untracked),
        "status_short": str(status.get("stdout", "")).splitlines(),
        "stderr": "\n".join(
            part for part in [str(branch.get("stderr", "")).strip(), str(status.get("stderr", "")).strip()] if part
        ),
    }


def repo_diff(repo: str | Path | None, max_chars: int = 120_000) -> dict[str, object]:
    if not repo:
        return {"ok": False, "error": "No repo configured"}
    path = Path(repo).expanduser().resolve()
    diff = _run_git(path, ["diff", "--", "."], timeout=20.0)
    text = str(diff.get("stdout", ""))
    truncated = len(text) > max_chars
    return {
        "ok": bool(diff["ok"]),
        "repo": str(path),
        "diff": text[:max_chars],
        "truncated": truncated,
        "stderr": diff.get("stderr", ""),
    }
