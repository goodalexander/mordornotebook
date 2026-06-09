import subprocess
from pathlib import Path

from mordornotebook.agent.cursor import CursorAgent


def test_cursor_exec_argv_uses_headless_workspace_defaults(tmp_path):
    agent = CursorAgent(repo=tmp_path, session_name="mordor-test", cursor_command="cursor-agent")

    argv = agent._cursor_exec_argv(tmp_path)

    assert argv[:2] == ["cursor-agent", "--print"]
    assert "--output-format" in argv
    assert argv[argv.index("--output-format") + 1] == "stream-json"
    assert "--stream-partial-output" in argv
    assert "--workspace" in argv
    assert argv[argv.index("--workspace") + 1] == str(tmp_path)
    assert "--trust" in argv
    assert "--sandbox" in argv
    assert "--force" in argv


def test_cursor_exec_argv_honors_explicit_output_format(tmp_path):
    agent = CursorAgent(repo=tmp_path, session_name="mordor-test", cursor_command="cursor-agent --output-format json")

    argv = agent._cursor_exec_argv(tmp_path)

    assert argv.count("--output-format") == 1
    assert argv[argv.index("--output-format") + 1] == "json"
    assert "--stream-partial-output" not in argv


def test_cursor_send_starts_headless_tmux_session(monkeypatch, tmp_path):
    calls = []

    monkeypatch.setenv("MORDOR_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("MORDOR_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")

    def fake_run(args, input_text=None, timeout=10.0):
        calls.append(args)
        if args[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(args, 1, "", "")
        if args[:2] == ["tmux", "new-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    agent = CursorAgent(repo=tmp_path, session_name="mordor-test", cursor_command="cursor-agent", cursor_sandbox="disabled")
    monkeypatch.setattr(agent, "_run", fake_run)

    result = agent.send("hello cursor")

    assert result["ok"] is True
    assert result["backend"] == "cursor"
    prompt_path = Path(result["prompt_path"])
    assert prompt_path.read_text(encoding="utf-8") == "hello cursor"
    new_session = next(call for call in calls if call[:2] == ["tmux", "new-session"])
    command = new_session[-1]
    assert "cursor-agent" in command
    assert "--print" in command
    assert "--output-format" in command
    assert "stream-json" in command
    assert "--workspace" in command
    assert "--trust" in command
    assert "--sandbox" in command
    assert "< " in command
    assert "MORDOR_AGENT_EXIT_CODE" in command


def test_cursor_send_refuses_existing_session(monkeypatch, tmp_path):
    def fake_run(args, input_text=None, timeout=10.0):
        if args[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    agent = CursorAgent(repo=tmp_path, session_name="mordor-test", cursor_command="cursor-agent")
    monkeypatch.setattr(agent, "_run", fake_run)

    result = agent.send("hello")

    assert result["ok"] is False
    assert result["backend"] == "cursor"
    assert "already exists" in result["error"]


def test_cursor_capture_prefers_raw_ndjson_over_wrapped_tmux(monkeypatch, tmp_path):
    monkeypatch.setenv("MORDOR_STATE_DIR", str(tmp_path / "state"))
    transcript_dir = tmp_path / "state" / "transcripts"
    transcript_dir.mkdir(parents=True)
    raw_path = transcript_dir / "mordor-test.cursor.ndjson"
    raw_path.write_text('{"result":"MORDOR_NOTEBOOK_DONE cursor-smoke"}\n', encoding="utf-8")

    def fake_run(args, input_text=None, timeout=10.0):
        if args[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(args, 0, "", "")
        if args[:2] == ["tmux", "capture-pane"]:
            return subprocess.CompletedProcess(args, 0, "MORDOR_NOTEBOOK_D\nONE cursor-smoke\nMORDOR_AGENT_EXIT_CODE=0\n", "")
        return subprocess.CompletedProcess(args, 0, "", "")

    agent = CursorAgent(repo=tmp_path, session_name="mordor-test", cursor_command="cursor-agent")
    monkeypatch.setattr(agent, "_run", fake_run)

    result = agent.capture()

    assert result["ok"] is True
    assert 'MORDOR_NOTEBOOK_DONE cursor-smoke' in result["text"]
    assert "MORDOR_AGENT_EXIT_CODE=0" in result["text"]
