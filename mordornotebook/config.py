"""Safe local configuration for Mordor Notebook."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
import stat
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    tomllib = None

from mordornotebook import paths


@dataclass
class MordorConfig:
    default_repo: str | None = None
    agent_backend: str = "codex"
    codex_command: str = "codex"
    cursor_command: str = "cursor-agent"
    cursor_model: str | None = None
    cursor_sandbox: str = "disabled"
    cursor_force: bool = True
    tmux_prefix: str = "mordor"
    context_max_chars: int = 200_000
    notebook_output_max_chars: int = 4_000
    memory_sample_rows: int = 5
    extra: dict[str, object] = field(default_factory=dict)


def _parse_toml(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    if tomllib is None:
        raise RuntimeError("tomllib is unavailable; use Python 3.11+ or install toml")
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return data if isinstance(data, dict) else {}


def load_config(path: Path | None = None) -> MordorConfig:
    path = path or paths.config_path()
    raw = _parse_toml(path)
    known = {field.name for field in MordorConfig.__dataclass_fields__.values()}
    kwargs = {key: value for key, value in raw.items() if key in known and key != "extra"}
    extra = {key: value for key, value in raw.items() if key not in known}
    config = MordorConfig(**kwargs)
    env_default_repo = os.environ.get("MORDOR_REPO") or os.environ.get("MORDOR_DEFAULT_REPO")
    if env_default_repo and not config.default_repo:
        config.default_repo = env_default_repo
    config.extra.update(extra)
    return config


def save_config(config: MordorConfig, path: Path | None = None) -> Path:
    paths.ensure_base_dirs()
    path = path or paths.config_path()
    payload = asdict(config)
    payload.pop("extra", None)
    lines = []
    for key, value in payload.items():
        if value is None:
            continue
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
        elif isinstance(value, bool):
            lines.append(f"{key} = {'true' if value else 'false'}")
        else:
            lines.append(f"{key} = {value}")
    for key, value in config.extra.items():
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f'{key} = "{escaped}"')
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def secrets_permissions_status(path: Path | None = None) -> dict[str, object]:
    path = path or paths.secrets_path()
    if not path.exists():
        return {"path": str(path), "exists": False, "secure": True, "mode": None}
    mode = stat.S_IMODE(path.stat().st_mode)
    insecure = bool(mode & (stat.S_IRWXG | stat.S_IRWXO))
    return {
        "path": str(path),
        "exists": True,
        "secure": not insecure,
        "mode": oct(mode),
    }


def apply_secret_file_permissions(path: Path | None = None) -> Path:
    path = path or paths.secrets_path()
    if not path.exists():
        paths.ensure_base_dirs()
        path.touch(mode=0o600, exist_ok=True)
    os.chmod(path, 0o600)
    return path
