# Install A Fresh Instance

This page is the user-facing quickstart for a new Mordor Notebook checkout.

## Requirements

- Linux host with Python 3.11+.
- `tmux` installed and available on `PATH`.
- JupyterLab 4.x in the environment where notebooks run.
- At least one local agent CLI:
  - Codex CLI for the default backend.
  - Cursor Agent CLI for the optional Cursor backend.
- The agent CLI must already be authenticated on the same Linux account that
  runs Jupyter. Mordor does not log in to Codex or Cursor for you.

## Install

```bash
git clone https://github.com/goodalexander/mordornotebook.git
cd mordornotebook

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[notebook,test]'
```

Run the local health check:

```bash
mordorctl doctor
```

Enable the Jupyter Server extension in the same environment that will run
Jupyter:

```bash
mordorctl jupyter enable --sys-prefix
jupyter server extension list
```

Restart Jupyter after enabling the extension. Then start JupyterLab normally:

```bash
jupyter lab
```

## Agent Login Checks

Codex must be installed and authenticated outside Mordor first. A practical
check is:

```bash
codex --help
mordorctl doctor --json
```

Cursor is optional. If you want to use it:

```bash
cursor-agent status
mordorctl doctor --json
```

`mordorctl doctor --json` reports whether the executables are visible and, for
Cursor, whether the CLI status probe says it is authenticated.

## Configure Defaults

Mordor reads config from `~/.config/mordornotebook/config.toml` and state from
`~/.local/state/mordornotebook/`.

The most common settings are:

```toml
default_repo = "/path/to/repo"
agent_backend = "codex"
codex_command = "codex"
cursor_command = "cursor-agent"
cursor_sandbox = "disabled"
cursor_force = true
```

You can also set the default repo with an environment variable:

```bash
export MORDOR_REPO=/path/to/repo
```

## Use In JupyterLab

1. Open a notebook in JupyterLab.
2. Click the `Mordor` top-menu item or notebook toolbar button.
3. Mordor silently attaches to the active kernel and opens the prompt panel.
4. Choose `Codex` or `Cursor`.
5. Type the request and click `Send`.

The button does not insert a bootstrap cell. It runs a silent `attach(...)`
statement in the kernel, then renders the panel through the Jupyter Server
extension.

The explicit Python path is still available:

```python
from pathlib import Path

from mordornotebook import attach

mordor = attach(repo=Path.cwd(), goal="iterate on this notebook task")
mordor.panel()
```

Register in-memory objects when useful:

```python
mordor.register("panel", panel)
```

## What The Agent Sees

Mordor instructs the agent to use these commands instead of editing notebook
files directly:

```bash
mordorctl notebook context --json
mordorctl memory list --json
mordorctl memory inspect panel --head 20 --json
mordorctl helpers ensure --json
mordorctl helpers list --json
mordorctl cell insert --type markdown --text "## Mordor generated: summary"
mordorctl cells list --json
```

The live bridge exists only after `attach(...)` has run in a notebook or IPython
kernel. Without it, notebook cell operations are queued on disk and cannot be
rendered live until a JupyterLab panel applies them.
