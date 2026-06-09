"""Environment checks for Mordor Notebook."""

from __future__ import annotations

from dataclasses import dataclass, asdict
import importlib.metadata
from pathlib import Path
import shutil
import shlex
from typing import Any

try:
    import jupyter_core.paths as jupyter_paths
except Exception:  # pragma: no cover - optional dependency boundary
    jupyter_paths = None

from mordornotebook import paths
from mordornotebook.agent.cursor import CursorAgent
from mordornotebook.config import load_config, secrets_permissions_status
from mordornotebook.redaction import scan_file_for_secret_markers


@dataclass
class DoctorCheck:
    name: str
    ok: bool
    detail: str
    severity: str = "error"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _module_version(dist_name: str, import_name: str | None = None, severity: str = "error") -> DoctorCheck:
    import_name = import_name or dist_name
    try:
        version = importlib.metadata.version(dist_name)
        return DoctorCheck(import_name, True, version, "info")
    except importlib.metadata.PackageNotFoundError:
        return DoctorCheck(import_name, False, "not installed", severity)


def run_doctor() -> dict[str, Any]:
    paths.ensure_base_dirs()
    config = load_config()
    checks: list[DoctorCheck] = []
    for command in ["codex", "tmux"]:
        location = shutil.which(command)
        checks.append(DoctorCheck(command, location is not None, location or "not found"))
    cursor_argv = shlex.split(str(config.cursor_command or "cursor-agent"))
    cursor_exe = cursor_argv[0] if cursor_argv else "cursor-agent"
    cursor_location = shutil.which(cursor_exe)
    checks.append(DoctorCheck("cursor-agent", cursor_location is not None, cursor_location or "not found", "warning"))
    cursor_doctor: dict[str, Any] = {}
    if cursor_location:
        cursor_doctor = CursorAgent(cursor_command=config.cursor_command).doctor()
        auth_status = cursor_doctor.get("auth_status") or {}
        auth_ok = bool(auth_status.get("ok")) if isinstance(auth_status, dict) else False
        checks.append(DoctorCheck("cursor_auth", auth_ok, str(auth_status.get("detail") if isinstance(auth_status, dict) else auth_status), "warning"))
    checks.extend(
        [
            _module_version("jupyter_server", "jupyter_server", severity="warning"),
            _module_version("jupyterlab", "jupyterlab", severity="warning"),
            _module_version("ipython", "IPython", severity="warning"),
            _module_version("nbformat", "nbformat", severity="warning"),
        ]
    )
    for label, path in [
        ("config_dir", paths.config_dir()),
        ("state_dir", paths.state_dir()),
        ("sessions_dir", paths.sessions_dir()),
        ("notebook_ops_dir", paths.notebook_ops_dir()),
        ("transcripts_dir", paths.transcripts_dir()),
    ]:
        try:
            path.mkdir(parents=True, exist_ok=True)
            probe = path / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
            checks.append(DoctorCheck(label, True, str(path), "info"))
        except Exception as exc:
            checks.append(DoctorCheck(label, False, f"{path}: {exc}"))
    secret_status = secrets_permissions_status()
    checks.append(
        DoctorCheck(
            "secrets_permissions",
            bool(secret_status["secure"]),
            f"{secret_status['path']} mode={secret_status.get('mode')}",
            "warning",
        )
    )
    jupyter_secret_findings: list[dict[str, Any]] = []
    if jupyter_paths is not None:
        config_path = Path(jupyter_paths.jupyter_config_dir()) / "jupyter_notebook_config.py"
        jupyter_secret_findings = scan_file_for_secret_markers(config_path)
        if jupyter_secret_findings:
            checks.append(
                DoctorCheck(
                    "jupyter_config_secret_markers",
                    False,
                    f"{len(jupyter_secret_findings)} redacted secret-like marker(s) found in {config_path}",
                    "warning",
                )
            )
        else:
            checks.append(DoctorCheck("jupyter_config_secret_markers", True, f"none found in {config_path}", "info"))
    fatal_ok = all(check.ok for check in checks if check.severity == "error")
    return {
        "ok": fatal_ok,
        "checks": [check.to_dict() for check in checks],
        "cursor": cursor_doctor,
        "jupyter_config_secret_findings": jupyter_secret_findings,
    }
