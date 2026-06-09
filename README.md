# Mordor Notebook

Mordor Notebook is a JupyterLab workflow for using local agent CLIs from inside
an open notebook. The product goal is simple: type a request in the notebook UI,
let Codex or Cursor inspect the repo and the live kernel context, and have the
agent create rendered notebook cells instead of pasting long code into chat.

The current implementation includes:

- a JupyterLab menu/toolbar button named `Mordor`;
- a Jupyter Server extension under `/mordor/api/...`;
- an in-kernel runtime bridge started by `attach(...)`;
- `mordorctl`, the CLI agents use to inspect context, inspect registered memory,
  and insert notebook cells;
- Codex and Cursor Agent backends run through `tmux` for an auditable trail;
- a repo-local helper workspace convention under `mordor/` and `mordorhelper/`.

## Start Here

- [Install A Fresh Instance](docs/Install.md)
- [Architecture](docs/Architecture.md)
- [Codex And Cursor Backends](docs/Agent_Backends.md)
- [Current Status](docs/Status.md)
- [Helper Workspace](docs/Mordor_Helper_Workspace.md)

Historical design plans are still kept under [docs/plans](docs/plans/index.md),
but they are not the primary product documentation.

## Fresh Install

Requirements:

- Python 3.11+
- JupyterLab 4.x
- `tmux`
- an authenticated local Codex CLI and/or Cursor Agent CLI

Install from a fresh checkout:

```bash
git clone https://github.com/goodalexander/mordornotebook.git
cd mordornotebook

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e '.[notebook,test]'

mordorctl doctor
mordorctl jupyter enable --sys-prefix
jupyter server extension list
```

Restart Jupyter after enabling the server extension:

```bash
jupyter lab
```

Codex and Cursor must already be logged in on the box running Jupyter. Mordor
does not manage those credentials.

## Minimal Notebook Entry

The JupyterLab button is the normal entrypoint. The explicit Python entrypoint is
still useful for debugging:

```python
from pathlib import Path

from mordornotebook import attach

mordor = attach(repo=Path.cwd(), goal="iterate on this notebook task")
mordor.panel()
```

If you want the agent to see a large in-memory object without reloading it from
disk:

```python
mordor.register("panel", panel)
```

The old OpenRouter-based helper API is deprecated. Migration notes are in
[docs/legacy/Legacy_OpenRouter_Helper.md](docs/legacy/Legacy_OpenRouter_Helper.md).
