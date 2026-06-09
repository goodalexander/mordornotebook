# Codex And Cursor Backends

Mordor treats Codex and Cursor as local command line backends. Mordor is not an
authentication manager and does not broker API keys for either tool.

## Shared Assumptions

- The backend CLI is installed on the same Linux account that runs Jupyter.
- The backend CLI is already logged in or otherwise configured.
- `tmux` is installed.
- The target repo is readable and writable by the Jupyter process.
- The backend can run shell commands in the target repo.
- Notebook mutation must go through `mordorctl cell insert`.

The JupyterLab panel is the product UI. Codex and Cursor are execution engines
behind that panel.

## Codex Backend

Codex is the default backend.

Default command:

```toml
codex_command = "codex"
```

Browser override:

```javascript
localStorage.setItem("mordorAgentBackend", "codex")
localStorage.setItem("mordorCodexCommand", "codex --sandbox danger-full-access --ask-for-approval never")
```

Runtime behavior:

1. Mordor creates a per-request tmux session.
2. It runs `codex exec --cd <repo> ...`.
3. The prompt is provided through stdin from a prompt file.
4. Codex writes notebook cells with `mordorctl cell insert`.
5. Mordor captures the tmux pane and output-last-message transcript.

The adapter also has handling for Codex update/trust prompts when using the
interactive start path, but the managed prompt-box path uses `codex exec`.

## Cursor Backend

Cursor is optional.

Default command:

```toml
cursor_command = "cursor-agent"
cursor_sandbox = "disabled"
cursor_force = true
```

Browser override:

```javascript
localStorage.setItem("mordorAgentBackend", "cursor")
localStorage.setItem("mordorCursorCommand", "cursor-agent")
localStorage.setItem("mordorCursorModel", "")
localStorage.setItem("mordorCursorSandbox", "disabled")
localStorage.setItem("mordorCursorForce", "true")
```

Runtime behavior:

1. Mordor creates a per-request tmux session.
2. It runs `cursor-agent --print --output-format stream-json --workspace <repo>`
   unless equivalent flags are already present in `cursor_command`.
3. The prompt is provided through stdin from a prompt file.
4. Cursor writes notebook cells with `mordorctl cell insert`.
5. Mordor stores Cursor NDJSON and stderr captures under the transcript state
   directory.

Check auth with:

```bash
cursor-agent status
mordorctl doctor --json
```

## Done Marker Contract

Both backends receive the same instruction:

```text
MORDOR_NOTEBOOK_DONE <request-id>
```

The backend must print that marker only after it has inserted and verified the
requested notebook operations. The panel watches the transcript for the marker,
then drains queued notebook cells.

## Failure Modes

Common backend failures:

- CLI missing from `PATH`.
- CLI installed but not authenticated for the Jupyter user.
- Jupyter Server extension enabled but Jupyter not restarted.
- No active runtime bridge because `attach(...)` has not run in the notebook.
- Backend edits `.ipynb` files directly instead of using `mordorctl cell insert`.
- Backend completes without inserting a code cell when the user asked for a
  chart, calculation, or data inspection.

Use:

```bash
mordorctl doctor --json
mordorctl sessions list --json
mordorctl cells list --json
```

to inspect the active state.
