"""tmux-backed Cursor Agent adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import shlex
import shutil
import subprocess
import time

from mordornotebook import paths
from mordornotebook.agent.tmux import safe_session_name
from mordornotebook.config import load_config
from mordornotebook.redaction import redact_text


def _has_option(argv: list[str], *names: str) -> bool:
    prefixes = tuple(f"{name}=" for name in names)
    return any(item in names or item.startswith(prefixes) for item in argv)


@dataclass
class CursorAgent:
    repo: str | Path | None = None
    session_name: str | None = None
    cursor_command: str | None = None
    cursor_model: str | None = None
    cursor_sandbox: str | None = None
    cursor_force: bool | None = None

    def __post_init__(self) -> None:
        config = load_config()
        repo_name = Path(self.repo).name if self.repo else "default"
        self.session_name = self.session_name or safe_session_name(f"{config.tmux_prefix}-{repo_name}")
        self.cursor_command = self.cursor_command or config.cursor_command
        self.cursor_model = self.cursor_model if self.cursor_model is not None else config.cursor_model
        self.cursor_sandbox = self.cursor_sandbox if self.cursor_sandbox is not None else config.cursor_sandbox
        self.cursor_force = bool(config.cursor_force if self.cursor_force is None else self.cursor_force)

    def _run(self, args: list[str], input_text: str | None = None, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, text=True, input=input_text, capture_output=True, timeout=timeout, check=False)

    def _cursor_argv(self) -> list[str]:
        return shlex.split(str(self.cursor_command or "cursor-agent"))

    def _cursor_exec_argv(self, repo: Path) -> list[str]:
        argv = self._cursor_argv()
        if not argv:
            return []
        exe = argv[0]
        rest = argv[1:]
        if rest and rest[0] == "agent":
            rest = rest[1:]
        result = [exe, *rest]
        if not _has_option(result, "-p", "--print"):
            result.append("--print")
        added_stream_json = False
        if not _has_option(result, "--output-format"):
            result.extend(["--output-format", "stream-json"])
            added_stream_json = True
        if added_stream_json and "--stream-partial-output" not in result:
            result.append("--stream-partial-output")
        if not _has_option(result, "--workspace"):
            result.extend(["--workspace", str(repo)])
        if "--trust" not in result:
            result.append("--trust")
        if self.cursor_sandbox and not _has_option(result, "--sandbox"):
            result.extend(["--sandbox", str(self.cursor_sandbox)])
        if self.cursor_model and not _has_option(result, "-m", "--model"):
            result.extend(["--model", str(self.cursor_model)])
        if self.cursor_force and "--force" not in result and "-f" not in result and "--yolo" not in result:
            result.append("--force")
        return result

    def exists(self) -> bool:
        proc = self._run(["tmux", "has-session", "-t", str(self.session_name)], timeout=3.0)
        return proc.returncode == 0

    def doctor(self) -> dict[str, object]:
        argv = self._cursor_argv()
        executable = shutil.which(argv[0]) if argv else None
        status: dict[str, object] = {"ok": False, "detail": "not checked"}
        version: str | None = None
        if executable:
            version_proc = self._run([argv[0], "--version"], timeout=5.0)
            if version_proc.returncode == 0:
                version = (version_proc.stdout or "").strip() or None
            status_proc = self._run([argv[0], "status", "--format", "json"], timeout=8.0)
            if status_proc.returncode == 0:
                try:
                    payload = json.loads(status_proc.stdout)
                    status = {
                        "ok": True,
                        "detail": {
                            "status": payload.get("status"),
                            "isAuthenticated": payload.get("isAuthenticated"),
                            "hasAccessToken": payload.get("hasAccessToken"),
                            "hasRefreshToken": payload.get("hasRefreshToken"),
                        },
                    }
                except json.JSONDecodeError:
                    status = {"ok": True, "detail": redact_text((status_proc.stdout or "").strip())}
            else:
                text_proc = self._run([argv[0], "status"], timeout=8.0)
                status = {
                    "ok": text_proc.returncode == 0,
                    "detail": redact_text(((text_proc.stdout or "") + (text_proc.stderr or "")).strip()),
                }
        return {
            "tmux": shutil.which("tmux"),
            "cursor": executable,
            "version": version,
            "session_name": self.session_name,
            "auth_status": status,
        }

    def start(self) -> dict[str, object]:
        if shutil.which("tmux") is None:
            return {"ok": False, "backend": "cursor", "error": "tmux executable not found"}
        argv = self._cursor_argv()
        if not argv or shutil.which(argv[0]) is None:
            return {"ok": False, "backend": "cursor", "error": f"{self.cursor_command} executable not found"}
        return {
            "ok": True,
            "backend": "cursor",
            "session_name": self.session_name,
            "ready": True,
            "mode": "headless_exec_on_send",
        }

    def send(self, prompt: str) -> dict[str, object]:
        if self.exists():
            return {
                "ok": False,
                "backend": "cursor",
                "session_name": self.session_name,
                "error": "Cursor tmux session already exists for this request",
            }
        return self._send_exec(prompt)

    def _send_exec(self, prompt: str) -> dict[str, object]:
        if shutil.which("tmux") is None:
            return {"ok": False, "backend": "cursor", "error": "tmux executable not found"}
        repo = Path(self.repo or Path.cwd()).expanduser().resolve()
        cursor_argv = self._cursor_exec_argv(repo)
        if not cursor_argv or shutil.which(cursor_argv[0]) is None:
            return {"ok": False, "backend": "cursor", "error": f"{self.cursor_command} executable not found"}
        paths.ensure_base_dirs()
        prompts_dir = paths.state_dir() / "agent_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompts_dir / f"{self.session_name}.cursor.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        output_path = paths.transcripts_dir() / f"{self.session_name}.cursor.ndjson"
        stderr_path = paths.transcripts_dir() / f"{self.session_name}.cursor.stderr.log"
        exec_command = " ".join(shlex.quote(str(part)) for part in cursor_argv)
        shell_command = (
            "set -o pipefail; "
            f"{exec_command} < {shlex.quote(str(prompt_path))} "
            f"2> {shlex.quote(str(stderr_path))} | tee {shlex.quote(str(output_path))}; "
            "status=${PIPESTATUS[0]}; "
            "echo; "
            "if [ -s " + shlex.quote(str(stderr_path)) + " ]; then "
            "echo MORDOR_CURSOR_STDERR_BEGIN; "
            "tail -200 " + shlex.quote(str(stderr_path)) + "; "
            "echo MORDOR_CURSOR_STDERR_END; "
            "fi; "
            "echo MORDOR_AGENT_EXIT_CODE=$status; "
            "while true; do sleep 3600; done"
        )
        command = "bash -lc " + shlex.quote(shell_command)
        proc = self._run(["tmux", "new-session", "-d", "-s", str(self.session_name), "-c", str(repo), command], timeout=10.0)
        return {
            "ok": proc.returncode == 0,
            "backend": "cursor",
            "session_name": self.session_name,
            "exec_mode": True,
            "prompt_path": str(prompt_path),
            "transcript_path": str(output_path),
            "stderr_path": str(stderr_path),
            "stdout": redact_text(proc.stdout),
            "stderr": redact_text(proc.stderr),
        }

    def capture(self, lines: int = 200) -> dict[str, object]:
        if not self.exists():
            return {"ok": False, "backend": "cursor", "session_name": self.session_name, "error": "tmux session does not exist"}
        proc = self._run(
            ["tmux", "capture-pane", "-t", str(self.session_name), "-p", "-S", f"-{int(lines)}"],
            timeout=5.0,
        )
        paths.ensure_base_dirs()
        raw_output_path = paths.transcripts_dir() / f"{self.session_name}.cursor.ndjson"
        raw_stderr_path = paths.transcripts_dir() / f"{self.session_name}.cursor.stderr.log"
        parts: list[str] = []
        if raw_output_path.exists():
            parts.append(raw_output_path.read_text(encoding="utf-8", errors="replace"))
        if raw_stderr_path.exists() and raw_stderr_path.stat().st_size:
            parts.append("MORDOR_CURSOR_STDERR_BEGIN")
            parts.append(raw_stderr_path.read_text(encoding="utf-8", errors="replace"))
            parts.append("MORDOR_CURSOR_STDERR_END")
        pane_text = proc.stdout or ""
        exit_lines = [line for line in pane_text.splitlines() if line.startswith("MORDOR_AGENT_EXIT_CODE=")]
        if exit_lines:
            parts.extend(exit_lines[-1:])
        if not parts:
            parts.append(pane_text)
        text = redact_text("\n".join(part.rstrip("\n") for part in parts if part is not None))
        transcript_path = paths.transcripts_dir() / f"{self.session_name}.log"
        transcript_path.write_text(text, encoding="utf-8")
        return {
            "ok": proc.returncode == 0,
            "backend": "cursor",
            "session_name": self.session_name,
            "text": text,
            "transcript_path": str(transcript_path),
            "stderr": redact_text(proc.stderr),
        }

    def stop(self) -> dict[str, object]:
        if not self.exists():
            return {"ok": True, "backend": "cursor", "session_name": self.session_name, "stopped": False, "reason": "tmux session does not exist"}
        proc = self._run(["tmux", "kill-session", "-t", str(self.session_name)], timeout=5.0)
        return {
            "ok": proc.returncode == 0,
            "backend": "cursor",
            "session_name": self.session_name,
            "stopped": proc.returncode == 0,
            "stderr": redact_text(proc.stderr),
        }
