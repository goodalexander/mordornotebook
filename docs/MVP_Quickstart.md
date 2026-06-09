# Mordor Notebook MVP Quickstart

> Current status: this quickstart documents the prompt-box notebook workflow.
> The core prompt-to-live-cell path, managed agent fallback, chart/error states,
> stalled-agent timeout, and cancellation are verified. Richer arbitrary
> analysis prompt regression and packaged release mechanics are still tracked in
> [Mordor Notebook Usable Product Recovery Plan](plans/Mordor_Notebook_Usable_Product_Recovery_Plan.md)
> before calling the product finished.

## Install

```bash
cd <mordornotebook-repo>
python3 -m pip install -e .
mordorctl doctor
```

For the repo-local full environment:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[notebook,test]'
.venv/bin/mordorctl doctor
.venv/bin/mordorctl jupyter enable --sys-prefix
.venv/bin/jupyter server extension list
```

## Attach Inside A Notebook

The easiest path is the JupyterLab UI:

1. Open a notebook under `<nav-ui-base-url>/jlab/lab`.
2. Click the `Mordor` top-menu item or the `Mordor` notebook toolbar button.
3. Mordor silently attaches to the active kernel and opens the prompt panel in
   the current notebook. It does not insert a bootstrap cell.

The explicit Python path still works:

```python
from pathlib import Path

from mordornotebook import attach

mordor = attach(
    repo=Path.cwd(),
    goal="iterate on this notebook task",
)
mordor.register("panel", panel)
mordor.panel()
```

Type the request into the Mordor panel and click `Send`. The default panel does
not expose `Start Codex`, `Capture`, `Ops`, or `Insert Audit`; those are
internal mechanics. A `Stop` control appears only while a request is running.

On attach or managed-agent send, Mordor also prepares the repo-local helper
workspace:

```text
mordor/         # helper registry, rules, ignored runtime artifacts
mordorhelper/   # importable helper package for reusable notebook logic
```

Agents are instructed to check `mordor/helpers.json` before writing code and to
prefer thin notebook cells that call helpers from `mordorhelper/`.

The panel includes an `Agent` selector. `Codex` remains the default backend.
`Cursor` uses the local `cursor-agent` CLI in headless mode and must satisfy the
same notebook contract: generated cells are inserted through `mordorctl cell
insert` and rendered in the active notebook.

Useful browser settings:

```javascript
localStorage.setItem("mordorAgentBackend", "cursor")
localStorage.setItem("mordorCursorCommand", "cursor-agent")
localStorage.setItem("mordorCursorModel", "")
localStorage.setItem("mordorCursorSandbox", "disabled")
localStorage.setItem("mordorCursorForce", "true")
```

Cursor setup checks:

```bash
cursor-agent status
mordorctl doctor --json
```

## Commands Codex Uses Internally

```bash
mordorctl notebook context
mordorctl memory list
mordorctl memory inspect panel --head 20
mordorctl cell insert --type markdown --text "## Mordor Audit"
mordorctl visual pnl --object equity_curve
mordorctl memory slice panel --date 2026-06-05 --ticker AAPL
mordorctl repo status
```

The live in-kernel bridge exists only after `attach(...)` runs in a notebook or
IPython kernel. Without that bridge, cell operations are queued on disk instead
of being applied live.
