import subprocess
from pathlib import Path

from mordornotebook.agent.tmux import TmuxAgent, safe_session_name


def test_safe_session_name():
    assert safe_session_name("mordor repo/name") == "mordor-repo-name"


def test_tmux_agent_exists_uses_tmux(monkeypatch):
    calls = []

    def fake_run(args, text=True, input=None, capture_output=True, timeout=10.0, check=False):
        calls.append(args)
        return subprocess.CompletedProcess(args, 1, "", "missing")

    monkeypatch.setattr(subprocess, "run", fake_run)
    agent = TmuxAgent(repo=".", session_name="mordor-test")
    assert agent.exists() is False
    assert calls[0][:2] == ["tmux", "has-session"]


def test_dismiss_codex_update_prompt(monkeypatch):
    calls = []

    def fake_run(args, input_text=None, timeout=10.0):
        calls.append(args)
        if args[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(args, 0, "Update available\n2. Skip\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    agent = TmuxAgent(repo=".", session_name="mordor-test")
    monkeypatch.setattr(agent, "_run", fake_run)
    assert agent.dismiss_codex_update_prompt() is True
    assert ["tmux", "send-keys", "-t", "mordor-test", "2", "Enter"] in calls


def test_dismiss_codex_trust_prompt(monkeypatch):
    calls = []

    def fake_run(args, input_text=None, timeout=10.0):
        calls.append(args)
        if args[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(
                args,
                0,
                "Do you trust the contents of this directory?\n1. Yes, continue\n2. No, quit\n",
                "",
            )
        return subprocess.CompletedProcess(args, 0, "", "")

    agent = TmuxAgent(repo=".", session_name="mordor-test")
    monkeypatch.setattr(agent, "_run", fake_run)
    assert "trust" in agent.dismiss_codex_startup_prompts(prompt_types=("trust",))
    assert ["tmux", "send-keys", "-t", "mordor-test", "1", "Enter"] in calls


def test_startup_prompt_detection_ignores_stale_scrollback(monkeypatch):
    def fake_run(args, input_text=None, timeout=10.0):
        if args[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(
                args,
                0,
                "Update available\n2. Skip\n\nOpenAI Codex (v0.136.0)\n\n›\n\n  gpt-5.5 xhigh\n",
                "",
            )
        return subprocess.CompletedProcess(args, 0, "", "")

    agent = TmuxAgent(repo=".", session_name="mordor-test")
    monkeypatch.setattr(agent, "_run", fake_run)
    assert agent.dismiss_codex_startup_prompts() == []


def test_stop_kills_existing_tmux_session(monkeypatch):
    calls = []

    def fake_run(args, input_text=None, timeout=10.0):
        calls.append(args)
        if args[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["tmux", "kill-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 1, "", "unexpected")

    agent = TmuxAgent(repo=".", session_name="mordor-test")
    monkeypatch.setattr(agent, "_run", fake_run)

    assert agent.stop() == {
        "ok": True,
        "session_name": "mordor-test",
        "stopped": True,
        "stderr": "",
    }
    assert ["tmux", "kill-session", "-t", "mordor-test"] in calls


def test_send_uses_codex_exec_in_tmux_for_new_session(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setenv("MORDOR_STATE_DIR", str(tmp_path / "state"))

    def fake_run(args, input_text=None, timeout=10.0):
        calls.append(args)
        if args[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(args, 1, "", "")
        if args[:2] == ["tmux", "new-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    agent = TmuxAgent(
        repo=tmp_path,
        session_name="mordor-test",
        codex_command="codex --sandbox danger-full-access --ask-for-approval never --no-alt-screen",
    )
    monkeypatch.setattr(agent, "_run", fake_run)

    result = agent.send("hello")

    assert result["ok"] is True
    assert result["exec_mode"] is True
    prompt_path = Path(result["prompt_path"])
    assert prompt_path.read_text(encoding="utf-8") == "hello"
    new_session = next(call for call in calls if call[:2] == ["tmux", "new-session"])
    command = new_session[-1]
    assert "codex exec" in command
    assert "--no-alt-screen" not in command
    assert "--ask-for-approval" not in command
    assert "--output-last-message" in command
    assert "< " in command
