# Mordor Notebook

Mordor Notebook is the local agent-in-Jupyter workflow for iterating on
backtests without leaving the notebook. It gives a notebook kernel a small local
runtime bridge, exposes registered in-memory objects to `mordorctl`, and runs
Codex or Cursor Agent in an auditable managed session.

## Start Here

- [MVP Quickstart](MVP_Quickstart.md): install, enable the Jupyter Server
  extension, attach inside a notebook, and use the core commands.
- [Implementation Status](Implementation_Status.md): what is implemented,
  verification evidence, and known gaps.
- [Mordor Helper Workspace](Mordor_Helper_Workspace.md): repo-local helper
  convention for keeping notebooks thin and reusable.
- [Usable Product Recovery Plan](plans/Mordor_Notebook_Usable_Product_Recovery_Plan.md):
  the corrected product plan for making the notebook UI usable without asking
  the user to QA backend/debug behavior.
- [Production Plan](plans/Mordor_Notebook_Production_Plan.md): the stage-gated
  plan that the MVP was implemented against.
- [Remote QA Plan](plans/Mordor_Notebook_Remote_QA_Plan.md): required
  server/gateway/browser/notebook validation before calling Mordor done.
- [Representative QA Goal](plans/Mordor_Notebook_Representative_QA_Goal.md):
  the eight-notebook Codex/Cursor acceptance matrix for proving real research
  workflows without hard-coded repo paths or prompt keyword routers.
- [Cursor Agent Integration Plan](plans/Mordor_Notebook_Cursor_Agent_Integration_Plan.md):
  stage-gated plan for adding Cursor Agent as an alternate backend while
  preserving the live notebook-cell contract.

## Core Workflow

```python
import os

from mordornotebook import attach

mordor = attach(
    repo=os.environ["MORDOR_REPO"],
    goal="iterate on this backtest",
)
mordor.register("panel", panel)
mordor.panel()
```

In JupyterLab, the extension also exposes a `Mordor` top-menu item and a
notebook toolbar button that silently attaches to the active kernel and opens
the prompt panel without inserting a bootstrap cell.

The panel exposes the user-facing flow: choose `Codex` or `Cursor`, type a
prompt, click `Send`, and watch generated notebook cells appear in the current
notebook. Agents can still use the lower-level CLI internally:

```bash
mordorctl notebook context
mordorctl memory list
mordorctl memory inspect panel --head 20
mordorctl cell insert --type markdown --text "## Mordor Audit"
mordorctl visual pnl --object equity_curve
```

## Boundaries

The current prompt-box panel has verified live cell insertion/execution, hidden
Codex fallback, chart/error handling, stalled-agent timeout, cancellation, and
initial Cursor Agent backend plumbing. It is still not the final packaged
product. The remaining acceptance work is documented in the Usable Product
Recovery Plan and Cursor Agent Integration Plan: packaged release mechanics,
broader arbitrary prompt regression coverage, and browser-level Cursor
generated-cell QA.
