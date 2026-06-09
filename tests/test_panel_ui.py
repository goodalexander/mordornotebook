from mordornotebook.ui import panel_markup


class DummySession:
    def metadata(self):
        return {
            "session_id": "2cef6283-7658-450d-b767-46885079a901",
            "repo": "<navstrategies-repo>",
            "bridge_url": "http://127.0.0.1:41533",
        }


def test_panel_is_prompt_first_and_uses_jupyterlab_live_notebook_api():
    markup = panel_markup(DummySession())

    assert "data-mordor-product-panel" in markup
    assert "data-mordor-prompt" in markup
    assert "data-mordor-send" in markup
    assert "data-mordor-agent-select" in markup
    assert '<option value="codex">Codex</option>' in markup
    assert '<option value="cursor">Cursor</option>' in markup
    assert "window.mordorNotebookLab" in markup
    assert "lab().ask" in markup
    assert "Notebook cells rendered and saved" not in markup

    assert "Start Codex" not in markup
    assert "Capture" not in markup
    assert "Insert Audit" not in markup
    assert "Ops" not in markup


def test_panel_has_managed_agent_stop_and_stall_state():
    markup = panel_markup(DummySession())

    assert "data-mordor-stop" in markup
    assert "agent/stop" in markup
    assert "backend: activeAgentBackend || selectedBackend()" in markup
    assert "cursor_command: cursorCommand" in markup
    assert "const cursorForce = true" in markup
    assert "activeAgentSession" in markup
    assert "activeAgentBackend" in markup
    assert "agentTimeoutMs" in markup
    assert "agentStallMs" in markup
    assert "setStatus('Stalled', 'warn')" in markup
    assert "MORDOR_AGENT_EXIT_CODE" in markup
    assert "draining queued notebook cells" in markup
    assert "doneQuietCycles >= 2" in markup
    assert "mordorctl cells list --json" in markup
    assert "mordorctl helpers ensure --json" in markup
    assert "mordorctl helpers list --json" in markup
    assert "mordor/helpers.json" in markup
    assert "mordorhelper" in markup
    assert "not giant inline notebook code blocks" in markup
    assert "print this marker as a standalone line" in markup
    assert "agentCompletionSeen(captureText, doneMarker, donePattern)" in markup
    assert "jsonEventText(event).includes(doneMarker)" in markup
    assert "['assistant', 'result'].includes" in markup
    assert "captureText.includes(doneMarker)" not in markup
    assert "localStorage.getItem(key)" in markup


def test_panel_posts_browser_notebook_context_through_jupyter_server_api():
    markup = panel_markup(DummySession())

    assert "mordor/api/" in markup
    assert "session" in markup
    assert "browser_session" in markup
    assert "credentials: 'same-origin'" in markup

    assert "fetch(bridge" not in markup
    assert "bridge + path" not in markup
    assert "http://127.0.0.1:41533" not in markup
    assert "fetch(\"http://127.0.0.1:41533" not in markup
    assert "fetch('http://127.0.0.1:41533" not in markup


def test_panel_infers_jupyter_base_path_from_lab_url():
    markup = panel_markup(DummySession())

    assert "'/lab'" in markup
    assert "window.location.pathname" in markup
    assert "new URL(inferBase() + 'mordor/api/', window.location.origin)" in markup
