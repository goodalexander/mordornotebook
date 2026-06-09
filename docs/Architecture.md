# Architecture

Mordor Notebook has five active parts.

## Components

| Component | Code | Purpose |
| --- | --- | --- |
| JupyterLab extension | `mordornotebook/labextension_src/` | Adds the `Mordor` menu item and notebook toolbar button. Inserts and executes generated cells in the live notebook model. |
| Jupyter Server extension | `mordornotebook/server/__init__.py` | Exposes authenticated `/mordor/api/...` endpoints to the browser. Proxies browser requests to the active kernel bridge and agent adapters. |
| Runtime bridge | `mordornotebook/runtime.py` | Starts inside the active IPython kernel when `attach(...)` runs. Holds registered memory objects and accepts cell/context requests on localhost. |
| CLI bridge | `mordornotebook/cli.py` | Provides `mordorctl`, the command line interface that agents use from tmux. |
| Agent adapters | `mordornotebook/agent/` | Runs Codex or Cursor Agent in tmux-managed processes and captures transcripts. |

Persistent state lives under `~/.local/state/mordornotebook/`:

- `active_session.json`: active kernel/session metadata.
- `sessions/`: per-session metadata.
- `notebook_ops/`: queued cell operations.
- `transcripts/`: tmux/Codex/Cursor captures.
- `agent_prompts/`: prompt files passed to managed agents.

Config lives under `~/.config/mordornotebook/config.toml`.

## Open Panel Flow

1. The user clicks `Mordor` in JupyterLab.
2. The labextension starts the active kernel if needed.
3. The labextension runs a silent `attach(...)` command through
   `kernel.requestExecute(..., silent=True, store_history=False)`.
4. `attach(...)` starts the runtime bridge on `127.0.0.1:<dynamic-port>` and
   writes active session metadata.
5. The labextension posts browser notebook context to `/mordor/api/session`.
6. The labextension requests `/mordor/api/panel/markup`.
7. The server extension returns the panel HTML.
8. The labextension renders the panel in the current JupyterLab page.

No bootstrap code cell is inserted by the button.

## Prompt Flow

1. The user types a prompt and clicks `Send`.
2. The panel builds a managed-agent prompt containing the repo path, request id,
   active backend, and mandatory notebook-cell contract.
3. The panel calls `/mordor/api/agent/send`.
4. The server extension creates the selected agent adapter.
5. The adapter launches a tmux session and runs the backend command.
6. The backend inspects context through `mordorctl notebook context --json`,
   memory through `mordorctl memory ...`, and repo state through normal shell
   tools.
7. The backend creates notebook content by calling `mordorctl cell insert`.
8. Browser-bound cell operations are queued in `~/.local/state/mordornotebook`.
9. The panel polls `/mordor/api/notebook/ops`.
10. The labextension applies queued operations to the live JupyterLab notebook
    model, runs code cells when requested, saves the notebook, and acks the
    operation.
11. The agent prints `MORDOR_NOTEBOOK_DONE <request-id>` when it has verified
    its inserted operations.

The important boundary is that agents should not edit `.ipynb` files directly.
They create notebook cells through `mordorctl cell insert`, and the JupyterLab
extension applies those cells to the open document.

## Why tmux Is Still In The Design

tmux is the audit surface. Agent runs happen in named tmux sessions so the user
or another process can capture the transcript, inspect failures, and stop the
run. Mordor does not rely on tmux for notebook rendering; rendering is handled
by the JupyterLab extension.

## Runtime Memory

The runtime bridge can expose objects that are already loaded in the notebook
kernel:

```python
mordor.register("panel", panel)
```

Agents can inspect those objects with:

```bash
mordorctl memory list --json
mordorctl memory inspect panel --head 20 --json
```

This is for notebook-native workflows where large DataFrames or panels are
already in memory and should not be reloaded from disk just so an agent can see
their shape.

## Helper Workspace

On attach or agent send, Mordor prepares a repo-local workspace:

```text
<repo>/
  mordor/
    HELPERS.md
    helpers.json
  mordorhelper/
    __init__.py
    catalog.py
```

The agent contract says to check `mordor/helpers.json` before writing new code,
prefer small helpers under `mordorhelper/`, and keep generated notebook cells
thin. See [Helper Workspace](Mordor_Helper_Workspace.md).
