# Mordor Notebook Production Plan

## Objective

Build Mordor Notebook as a local, single-user Jupyter/IPython integration where a
Codex CLI agent runs in an auditable tmux session and can inspect/mutate the
currently open notebook, inspect live in-kernel data objects, and use normal repo
operations without the user leaving Jupyter.

The initial implementation target is not a Jupyter fork. It is a packaged
extension layer around Jupyter Server/JupyterLab, IPython, tmux, and Codex. The
usable product bar is now separately defined in
[Mordor Notebook Usable Product Recovery Plan](Mordor_Notebook_Usable_Product_Recovery_Plan.md).

## Current Baseline

Environment found on this machine:

- `codex` CLI is installed.
- `tmux 3.4` is installed.
- Jupyter stack is Jupyter Server 2.x, JupyterLab 4.x, IPython 9.x, nbformat
  5.x, ipykernel 7.x.
- Classic `notebook` package is not installed, so the primary UI target is
  JupyterLab.
- `codex-whip` exists locally and already has tmux/Codex pane discovery,
  capture, nudge, and keepalive logic that can be reused or mirrored.
- Existing Mordor Notebook is a Python package that reads notebook JSON from
  disk, exports repository files into prompt context, and uses OpenRouter to
  generate code into `IPython.set_next_input`.

Risk found:

- Current Jupyter config stores credential material directly and appears malformed
  around repo-list configuration. Production Mordor should move secrets to a
  dedicated local config/credential file and avoid writing API keys into Jupyter
  config.

Deprecation decision:

- The current OpenRouter helper stack is legacy and should not constrain the MVP:
  - `mordornotebook.wrangling.jupyter_tool.UserQuery`;
  - `mordornotebook.wrangling.repo_export`;
  - `mordornotebook.ai.openrouter.OpenRouterTool`;
  - `mordornotebook.settings.*` helpers that mutate Jupyter config.
- These modules may be kept behind a legacy namespace temporarily, but new
  architecture should replace them rather than preserve compatibility.
- The old repo-export idea can survive only as a bounded, redacted context
  builder with `.mordorignore`, not as a whole-repo prompt dump.
- OpenRouter can remain an optional model backend later, but it is not the core
  product path. The core product path is local Codex CLI in tmux.

## Product Shape

The user-facing workflow should be:

```python
from mordornotebook import attach

mordor = attach(
    repo="<navstrategies-repo>",
    goal="iterate on this backtest",
)
mordor.register("panel", panel)
mordor.register("returns", returns)
```

Then, inside JupyterLab:

1. A Mordor side panel shows the tmux/Codex transcript.
2. The user sends Codex an instruction from the notebook UI.
3. Codex can run normal repo commands in the configured repo.
4. Codex can call `mordorctl` to inspect notebook cells, inspect registered
   in-memory packets, enqueue new markdown/code cells, and request visual
   notebook outputs.
5. The JupyterLab extension applies cell insertions to the live notebook model,
   not just to the `.ipynb` file on disk.
6. The user can audit everything from the notebook: prompt, tmux transcript,
   cell mutations, repo diff, and generated outputs.

## Architecture

### 1. Kernel Runtime

Package module: `mordornotebook.runtime`

Responsibilities:

- Attach to the active IPython kernel.
- Register named in-memory objects as memory packets.
- Summarize large objects safely:
  - DataFrame shape, columns, dtypes, index names/types, memory usage;
  - MultiIndex levels and sampled labels;
  - min/max date windows when detectable;
  - bounded `.head()`, `.tail()`, `.sample()`;
  - no full serialization of large objects by default.
- Execute bounded read-only inspection snippets in the active kernel when
  explicitly requested.
- Provide helpers for common quant/backtest inspection:
  - MultiIndex date/ticker slice preview;
  - event-window slice;
  - PnL/equity curve plot;
  - returns distribution;
  - parquet metadata and row-group summary;
  - dataframe profile section.

Important boundary:

- The agent must not automatically execute arbitrary destructive notebook code.
  Default behavior is to insert inspection cells for user execution. Explicit
  execution should require a visible `allow_execute=True` or UI confirmation.

### 2. Jupyter Server Extension

Package module: `mordornotebook.server`

Local HTTP endpoints, bound only to the active Jupyter server:

- `GET /mordor/api/health`
- `POST /mordor/api/session`
- `GET /mordor/api/notebook/context`
- `POST /mordor/api/notebook/cell`
- `GET /mordor/api/notebook/ops`
- `POST /mordor/api/notebook/ops/<id>/ack`
- `GET /mordor/api/memory`
- `POST /mordor/api/memory/inspect`
- `POST /mordor/api/agent/start`
- `POST /mordor/api/agent/send`
- `GET /mordor/api/agent/capture`
- `GET /mordor/api/repo/status`

The server extension owns durable state:

```text
~/.local/state/mordornotebook/
  sessions.sqlite
  transcripts/
  notebook_ops/
  logs/
```

It should not store raw secrets. It may store paths, kernel ids, notebook paths,
repo paths, tmux target names, operation ids, checksums, and redacted transcripts.

### 3. JupyterLab Frontend Extension

Package module/package: `mordornotebook.labextension`

Responsibilities:

- Render a side panel inside JupyterLab.
- Show the tmux transcript with polling first; xterm.js streaming can come later.
- Send prompts to the tmux/Codex session.
- Track the active notebook panel and selected cell.
- Pull pending cell operations from the server extension.
- Apply insertions via JupyterLab notebook model APIs.
- Acknowledge each operation after insertion/save.
- Show operation history: pending, applied, failed.

Why this is required:

- A Python server can edit an `.ipynb` file, but it cannot reliably mutate the
  open JupyterLab notebook model. The frontend extension is the reliable bridge
  for live cell insertion.

Fallback:

- If the JupyterLab extension is unavailable, `mordorctl cell insert` can append
  to disk with an explicit warning that the notebook must be reloaded. This is
  fallback-only, not the target UX.

### 4. tmux/Codex Agent Adapter

Package module: `mordornotebook.agent.tmux`

Responsibilities:

- Create or reuse a session named `mordor-<repo>-<kernel>`.
- Launch the Codex process with a stable command:

```text
codex --cd <repo> --no-alt-screen
```

- Record pane text with `tmux capture-pane`.
- Send prompt text with paste-buffer/send-keys.
- Keep a transcript log linked to the notebook session.
- Detect missing/exited Codex process.
- Use `codex-whip` mechanics where practical, or keep the adapter API
  compatible enough to swap later.

### 5. `mordorctl`

Package module: `mordornotebook.cli`

Installed console command:

```text
mordorctl
```

This is the key bridge for Codex. Codex inside tmux can call:

```text
mordorctl notebook context
mordorctl cells list
mordorctl cell insert --type code --after selected --file /tmp/cell.py
mordorctl cell insert --type markdown --after selected --text "## Audit"
mordorctl memory list
mordorctl memory inspect panel --head 20
mordorctl memory slice panel --date 2026-06-05 --ticker AAPL
mordorctl visual pnl --series equity_curve
mordorctl repo status
mordorctl doctor
```

This gives the agent notebook-native capabilities without special Codex internals.

### 6. Context Builder

Package module: `mordornotebook.context`

Context packet should include:

- user goal and current prompt;
- active notebook path, selected cell index, unsaved/saved state if available;
- notebook source and bounded outputs;
- memory packet inventory and summaries;
- repo path, branch, dirty status, recent diff summary;
- relevant skill manifests, if available;
- recent Mordor operations/transcript tail;
- redaction report.

Do not include:

- full huge DataFrames;
- full binary outputs;
- API keys or credential files;
- huge notebook outputs unless explicitly requested.

## Stage-Gated Implementation Plan

### Stage 0: Repo And Config Hardening

Deliverables:

- Move packaging toward `pyproject.toml` or keep `setup.py` while adding
  `console_scripts` for `mordorctl`.
- Mark legacy OpenRouter/Jupyter-config helpers as deprecated and quarantine
  them from the new attach/CLI path.
- Add `mordornotebook doctor`.
- Add safe config module:
  - `~/.config/mordornotebook/config.toml`;
  - `~/.config/mordornotebook/secrets.toml` or environment variable support;
  - file permissions check for secrets.
- Stop writing API keys into Jupyter config.
- Add `.mordorignore` support for repo/context exports.
- Add tests for config parsing and redaction.

Gate:

```text
pip install -e .
mordorctl doctor
pytest
```

Pass criteria:

- Doctor detects `codex`, `tmux`, Jupyter Server, JupyterLab, IPython, and
  writable state/config dirs.
- Doctor warns, but does not print, if existing Jupyter config contains secrets.
- Tests pass without network or model calls.

### Stage 1: Notebook State And Memory Bridge

Deliverables:

- `from mordornotebook import attach`
- `mordor.register(name, obj)`
- memory packet summaries for pandas DataFrame/Series, pathlib paths, and basic
  Python objects;
- `mordorctl memory list`;
- `mordorctl memory inspect <name>`;
- `mordorctl notebook context` with bounded notebook and memory summaries.

Gate:

In a notebook:

```python
import pandas as pd
from mordornotebook import attach

mordor = attach(repo="<navstrategies-repo>")
panel = pd.DataFrame({"ticker": ["AAPL", "MSFT"], "pnl": [1.0, -0.5]})
mordor.register("panel", panel)
```

Then from shell:

```text
mordorctl memory list
mordorctl memory inspect panel --head 2
mordorctl notebook context
```

Pass criteria:

- The registered object appears by name.
- Inspection output is bounded and does not serialize the full object.
- Notebook context includes cells, outputs, repo, and memory inventory.

### Stage 2: Cell Operation Queue And Live Notebook Mutation

Deliverables:

- Server-side operation queue for cell insertions.
- JupyterLab extension that:
  - discovers active notebook;
  - applies queued cell insertions;
  - acknowledges success/failure.
- `mordorctl cell insert` command.
- Markdown section insertion helper.

Gate:

```text
mordorctl cell insert --type markdown --after selected --text "## Mordor Audit"
mordorctl cell insert --type code --after selected --text "panel.head()"
```

Pass criteria:

- Cells appear in the open notebook without manually editing the file.
- Operation log records requested/applied timestamps.
- Failed insertions remain visible with an error message and can be retried.

### Stage 3: tmux/Codex Side Panel

Deliverables:

- tmux session start/reuse.
- Codex process start/reuse inside tmux.
- Side panel transcript view.
- Prompt input box.
- `mordorctl agent start/send/capture`.
- Transcript saved under state dir.

Gate:

From JupyterLab side panel:

1. click/start Mordor Codex;
2. send: "Read the notebook context and insert a markdown audit section";
3. Codex calls `mordorctl notebook context`;
4. Codex calls `mordorctl cell insert`;
5. notebook receives the cell.

Pass criteria:

- No external terminal/iTerm/tmux attach is required.
- Transcript is visible in JupyterLab.
- The tmux pane can be inspected later with normal `tmux attach` if needed.

### Stage 4: Backtest Visual Inspection Primitives

Deliverables:

- `mordorctl visual pnl --object <name> [--column <col>]`
- `mordorctl memory slice` for MultiIndex and date/ticker panels.
- `mordorctl visual event-window`.
- generated cells include:
  - imports;
  - bounded slice logic;
  - plot code;
  - title/subtitle with source object and date window;
  - no destructive mutation.

Gate:

Given a registered returns/equity curve object:

```text
mordorctl visual pnl --object equity_curve
mordorctl memory slice panel --date 2026-06-05 --ticker AAPL
```

Pass criteria:

- Generated cells run in the notebook.
- Plots render inline with matplotlib.
- MultiIndex inspection code handles missing dates/tickers gracefully.

### Stage 5: Repo Integration And Commit Flow

Deliverables:

- `mordorctl repo status/diff`.
- Context includes branch, dirty state, and untracked count.
- Codex prompt bootstrap instructs agent:
  - do not revert user work;
  - use repo tests;
  - use `mordorctl` for notebook operations;
  - do not commit notebooks unless requested.
- Optional `mordorctl repo commit --message ...` with explicit confirmation.

Gate:

Codex can:

1. inspect notebook context;
2. edit repo files using normal shell;
3. run tests;
4. insert notebook follow-on cells;
5. show git diff/status in the notebook.

Pass criteria:

- Repo changes are auditable from both git and notebook transcript.
- Notebook mutations and file edits are separately recorded.

### Stage 6: Production-ish Hardening

Deliverables:

- `mordorctl doctor --json`.
- session cleanup command:

```text
mordorctl sessions list
mordorctl sessions cleanup --older-than 7d
```

- logs with redaction;
- operation replay/export;
- basic docs and README quickstart;
- tests for:
  - config;
  - memory summaries;
  - notebook op queue;
  - tmux adapter with mocked subprocess;
  - CLI contract.

Gate:

```text
pytest
mordorctl doctor
python -m mordornotebook.smoke
```

Pass criteria:

- A fresh install can launch JupyterLab, attach a notebook, start Codex in tmux,
  send a prompt, and insert a cell.
- Failures are visible in UI and logs.
- No secrets are printed in logs or context packets.

## Single-Run `/goal` Scope

Recommended `/goal` objective:

```text
Implement Mordor Notebook MVP in <mordornotebook-repo>:
create the config/doctor/CLI, kernel attach + memory registry, notebook context
builder, cell operation queue, minimal JupyterLab side panel or injected lab
bridge sufficient to apply queued cells, tmux/Codex start/capture/send adapter,
and docs/tests. Acceptance: from a JupyterLab notebook I can attach Mordor,
register a DataFrame, start Codex in an embedded tmux-backed side panel, have
Codex inspect notebook/memory via mordorctl, and have Codex insert a markdown or
code cell into the live notebook without leaving Jupyter.
```

Minimum green gates for "prod-ish after one run":

1. Stage 0 doctor/config passes.
2. Stage 1 memory/context works.
3. Stage 2 live cell insertion works.
4. Stage 3 tmux/Codex capture/send works.
5. Stage 4 has at least PnL plot and MultiIndex slice cell generators.

Stage 5 commit flow and Stage 6 cleanup can be partial as long as they are not
blocking or unsafe.

## Failure Modes And Controls

| Risk | Failure Mode | Control |
|---|---|---|
| JupyterLab frontend API mismatch | cell insertion silently fails | operation queue with ack/error, version-gated frontend tests, disk append fallback with warning |
| notebook has unsaved changes | raw `.ipynb` write loses user state | frontend applies to live model; server does not overwrite active notebook |
| kernel busy or dead | memory inspect hangs | timeout, interrupt option, clear error in UI |
| huge DataFrames/parquets | context explosion or memory pressure | summaries only, bounded samples, explicit opt-in for large export |
| MultiIndex assumptions wrong | slice code errors | generated cells include index-name discovery, graceful missing-label handling |
| Codex CLI missing/auth broken | side panel appears dead | doctor checks, start failure surfaced, transcript logs stderr |
| tmux session orphaned | stale sessions accumulate | deterministic session names, sessions list/cleanup |
| secrets in notebook/config | prompt/log credential leak | redaction filters, `.mordorignore`, never print secret values, config migration warning |
| remote Jupyter exposure | arbitrary local command endpoint exposed | bind to Jupyter auth/session, localhost-only assumptions, per-session token |
| multiple notebooks attached | operations applied to wrong notebook | active notebook id, kernel id, notebook path, operation target checksum |
| agent over-edits notebook | untrusted generated code runs | insert-only by default, user executes cells unless explicit execution approved |
| dirty repo | Codex overwrites user work | repo status in context, no automatic reset, explicit commit controls |
| dependency drift | extension breaks on future JupyterLab | pin tested version range, doctor warns outside range |

## Non-Goals For MVP

- Full hosted multi-user notebook service.
- General dashboard builder.
- Forking IPython/Jupyter.
- Browser-independent support beyond current JupyterLab.
- Automatic execution of generated cells without explicit approval.
- Committing notebooks or repo changes automatically.

## Implementation Order

1. Add config/doctor/CLI skeleton and tests.
2. Add runtime attach + memory registry.
3. Add context builder and redaction.
4. Add notebook operation queue.
5. Add minimal JupyterLab bridge for applying queued cell operations.
6. Add tmux adapter and transcript capture.
7. Add Codex bootstrap prompt and `mordorctl` command docs.
8. Add visual inspection commands.
9. Add smoke test and README quickstart.

## Smoke Scenario

```python
from mordornotebook import attach
import pandas as pd

mordor = attach(repo="<navstrategies-repo>", goal="audit pnl")
panel = pd.DataFrame(
    {"ticker": ["AAPL", "MSFT"], "trade_date": ["2026-06-05", "2026-06-05"], "pnl": [1.2, -0.4]}
)
mordor.register("panel", panel)
```

Then in the Mordor side panel:

```text
Inspect the registered panel and insert a section with a pandas slice and a PnL
plot cell. Do not execute the generated cells.
```

Expected result:

- tmux transcript shows Codex using `mordorctl memory list/inspect`;
- two cells are inserted:
  - markdown heading;
  - code cell with bounded inspection/plot code;
- repo status is visible;
- no external terminal is required.
