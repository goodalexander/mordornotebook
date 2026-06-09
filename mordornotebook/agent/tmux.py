"""tmux-backed Codex adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import time
import uuid

from mordornotebook import paths
from mordornotebook.config import load_config
from mordornotebook.redaction import redact_text


def safe_session_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.:-]+", "-", value).strip("-")
    return cleaned[:80] or "mordor"


@dataclass
class TmuxAgent:
    repo: str | Path | None = None
    session_name: str | None = None
    codex_command: str | None = None

    def __post_init__(self) -> None:
        config = load_config()
        repo_name = Path(self.repo).name if self.repo else "default"
        self.session_name = self.session_name or safe_session_name(f"{config.tmux_prefix}-{repo_name}")
        self.codex_command = self.codex_command or config.codex_command

    def _run(self, args: list[str], input_text: str | None = None, timeout: float = 10.0) -> subprocess.CompletedProcess[str]:
        return subprocess.run(args, text=True, input=input_text, capture_output=True, timeout=timeout, check=False)

    def doctor(self) -> dict[str, object]:
        codex_argv = self._codex_argv()
        return {
            "tmux": shutil.which("tmux"),
            "codex": shutil.which(codex_argv[0]) if codex_argv else None,
            "session_name": self.session_name,
        }

    def _codex_argv(self) -> list[str]:
        return shlex.split(str(self.codex_command or "codex"))

    def _codex_exec_argv(self, repo: Path) -> list[str]:
        argv = self._codex_argv()
        if not argv:
            return []
        exe = argv[0]
        rest = argv[1:]
        if rest and rest[0] == "exec":
            rest = rest[1:]
        filtered: list[str] = []
        skip_next = False
        options_with_values = {"--cd", "-C", "--ask-for-approval", "-a"}
        for item in rest:
            if skip_next:
                skip_next = False
                continue
            if item == "--no-alt-screen":
                continue
            if item in options_with_values:
                skip_next = True
                continue
            if item.startswith("--cd="):
                continue
            if item.startswith("--ask-for-approval="):
                continue
            filtered.append(item)
        return [exe, "exec", *filtered, "--cd", str(repo), "--color", "never", "-"]

    def exists(self) -> bool:
        proc = self._run(["tmux", "has-session", "-t", str(self.session_name)], timeout=3.0)
        return proc.returncode == 0

    def start(self) -> dict[str, object]:
        if shutil.which("tmux") is None:
            return {"ok": False, "error": "tmux executable not found"}
        codex_argv = self._codex_argv()
        if not codex_argv or shutil.which(codex_argv[0]) is None:
            return {"ok": False, "error": f"{self.codex_command} executable not found"}
        if self.exists():
            dismissed = self.dismiss_codex_startup_prompts()
            return {"ok": True, "session_name": self.session_name, "reused": True, "dismissed_startup_prompts": dismissed}
        repo = Path(self.repo or Path.cwd()).expanduser().resolve()
        command_parts = [*codex_argv, "--cd", str(repo), "--no-alt-screen"]
        command = " ".join(shlex.quote(str(part)) for part in command_parts)
        proc = self._run(
            ["tmux", "new-session", "-d", "-s", str(self.session_name), "-c", str(repo), command],
            timeout=10.0,
        )
        dismissed = False
        if proc.returncode == 0:
            time.sleep(0.75)
            dismissed = self.dismiss_codex_startup_prompts()
        return {
            "ok": proc.returncode == 0,
            "session_name": self.session_name,
            "reused": False,
            "dismissed_startup_prompts": dismissed,
            "stdout": redact_text(proc.stdout),
            "stderr": redact_text(proc.stderr),
        }

    def dismiss_codex_update_prompt(self) -> bool:
        return bool(self.dismiss_codex_startup_prompts(prompt_types=("update",)))

    def dismiss_codex_startup_prompts(self, prompt_types: tuple[str, ...] = ("update", "trust")) -> list[str]:
        dismissed: list[str] = []
        for _ in range(4):
            action = self._next_startup_prompt_action(prompt_types=prompt_types)
            if action is None:
                break
            self._run(["tmux", "send-keys", "-t", str(self.session_name), action, "Enter"], timeout=5.0)
            dismissed.append("update" if action == "2" else "trust")
            time.sleep(0.75)
        return dismissed

    def _next_startup_prompt_action(self, prompt_types: tuple[str, ...]) -> str | None:
        if not self.exists():
            return None
        proc = self._run(
            ["tmux", "capture-pane", "-t", str(self.session_name), "-p", "-S", "-80"],
            timeout=5.0,
        )
        text = proc.stdout or ""
        if "OpenAI Codex" in text and re.search(r"\n\s*›\s*(\n|$)", text):
            return None
        if "update" in prompt_types and "Update available" in text and "Skip" in text:
            return "2"
        if (
            "trust" in prompt_types
            and "Do you trust the contents of this directory" in text
            and "Yes, continue" in text
        ):
            return "1"
        return None

    def send(self, prompt: str) -> dict[str, object]:
        if not self.exists():
            return self._send_exec(prompt)
        buffer_name = f"mordor-{uuid.uuid4()}"
        load = self._run(["tmux", "load-buffer", "-b", buffer_name, "-"], input_text=prompt, timeout=5.0)
        if load.returncode != 0:
            return {"ok": False, "error": redact_text(load.stderr)}
        paste = self._run(["tmux", "paste-buffer", "-b", buffer_name, "-t", str(self.session_name)], timeout=5.0)
        submit = self._submit_pasted_prompt()
        self._run(["tmux", "delete-buffer", "-b", buffer_name], timeout=3.0)
        return {
            "ok": paste.returncode == 0 and submit.get("ok", False),
            "session_name": self.session_name,
            "stderr": redact_text(paste.stderr + str(submit.get("stderr", ""))),
            "submit_attempts": submit.get("attempts"),
        }

    def _send_exec(self, prompt: str) -> dict[str, object]:
        if shutil.which("tmux") is None:
            return {"ok": False, "error": "tmux executable not found"}
        repo = Path(self.repo or Path.cwd()).expanduser().resolve()
        exec_argv = self._codex_exec_argv(repo)
        if not exec_argv or shutil.which(exec_argv[0]) is None:
            return {"ok": False, "error": f"{self.codex_command} executable not found"}
        paths.ensure_base_dirs()
        prompts_dir = paths.state_dir() / "agent_prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        prompt_path = prompts_dir / f"{self.session_name}.txt"
        prompt_path.write_text(prompt, encoding="utf-8")
        output_path = paths.transcripts_dir() / f"{self.session_name}.last_message.txt"
        exec_command = " ".join(shlex.quote(str(part)) for part in [*exec_argv[:-1], "--output-last-message", str(output_path), "-"])
        shell_command = (
            f"{exec_command} < {shlex.quote(str(prompt_path))}; "
            "status=$?; "
            "echo; "
            "echo MORDOR_AGENT_EXIT_CODE=$status; "
            "while true; do sleep 3600; done"
        )
        command = "bash -lc " + shlex.quote(shell_command)
        proc = self._run(["tmux", "new-session", "-d", "-s", str(self.session_name), "-c", str(repo), command], timeout=10.0)
        return {
            "ok": proc.returncode == 0,
            "session_name": self.session_name,
            "exec_mode": True,
            "prompt_path": str(prompt_path),
            "stdout": redact_text(proc.stdout),
            "stderr": redact_text(proc.stderr),
        }

    def _submit_pasted_prompt(self) -> dict[str, object]:
        last_stderr = ""
        for attempt in range(1, 5):
            proc = self._run(["tmux", "send-keys", "-t", str(self.session_name), "C-m"], timeout=5.0)
            last_stderr += proc.stderr
            time.sleep(0.35)
            capture = self._run(
                ["tmux", "capture-pane", "-t", str(self.session_name), "-p", "-S", "-80"],
                timeout=5.0,
            )
            text = capture.stdout or ""
            if "Working (" in text or re.search(r"\n[•◦] ", text):
                return {"ok": proc.returncode == 0, "attempts": attempt, "stderr": last_stderr}
        return {"ok": False, "attempts": 4, "stderr": last_stderr or "prompt did not enter Working state"}

    def capture(self, lines: int = 200) -> dict[str, object]:
        if not self.exists():
            return {"ok": False, "session_name": self.session_name, "error": "tmux session does not exist"}
        proc = self._run(
            ["tmux", "capture-pane", "-t", str(self.session_name), "-p", "-S", f"-{int(lines)}"],
            timeout=5.0,
        )
        text = redact_text(proc.stdout)
        paths.ensure_base_dirs()
        transcript_path = paths.transcripts_dir() / f"{self.session_name}.log"
        transcript_path.write_text(text, encoding="utf-8")
        return {
            "ok": proc.returncode == 0,
            "session_name": self.session_name,
            "text": text,
            "transcript_path": str(transcript_path),
            "stderr": redact_text(proc.stderr),
        }

    def stop(self) -> dict[str, object]:
        if not self.exists():
            return {"ok": True, "session_name": self.session_name, "stopped": False, "reason": "tmux session does not exist"}
        proc = self._run(["tmux", "kill-session", "-t", str(self.session_name)], timeout=5.0)
        return {
            "ok": proc.returncode == 0,
            "session_name": self.session_name,
            "stopped": proc.returncode == 0,
            "stderr": redact_text(proc.stderr),
        }
