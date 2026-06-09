# Mordor Notebook Usable Product Recovery Plan

## Purpose

This document replaces the previous "backend proof means usable" standard.
Mordor Notebook is not usable until a person can stay inside a Jupyter notebook,
type an instruction in natural language, see Codex working, and watch complete
notebook cells appear, execute, and render in the notebook they are looking at.

The current debug panel is not a usable product. It exposed implementation
controls and accepted a reload-based file mutation path as if that were the user
experience. That is not acceptable.

## Verified Progress On 2026-06-08

The default panel has now moved from the failed debug surface to a prompt-first
workflow:

- visible controls are `textarea` + `Send` + status/activity/generated-cells;
- `Start Codex`, `Capture`, `Ops`, and `Insert Audit` are no longer present in
  the default panel;
- the browser-visible JupyterLab notebook path is posted to the server and
  preserved on the active Mordor session;
- the JupyterLab labextension can insert cells through the active
  `NotebookPanel` and save through JupyterLab;
- generated code cells can execute in the active kernel and render inline;
- browser-bound `mordorctl cell insert` no longer edits the `.ipynb` file
  behind JupyterLab's back. It queues an operation for the browser labextension,
  which applies it live and acknowledges it as `live_applied`;
- unsupported local prompts fall back to a hidden per-request tmux/Codex
  session. The user still sees only Send/status/activity.
- a running request exposes a real `Stop` control; a cancelled request resolves
  to panel `Status: Cancelled`;
- stalled managed-agent requests become visible in the activity feed and fail
  with a bounded timeout instead of silently spinning;
- the browser QA harness includes deterministic fake-agent success,
  stall/timeout, and cancellation cases in addition to the live Codex smoke.

Verified browser smokes:

- Fresh-equity-universe prompt:
  `notebooks/qa_scratch/mordor_usable_product_smoke_after_agent_wiring.ipynb`
  gained a markdown audit cell and an executed code cell without reload. The
  code output showed `latest_trade_date = 2026-06-08`, `rows_loaded = 8204322`,
  and `symbols = 7645`.
- Generic hidden-Codex prompt:
  `notebooks/qa_scratch/mordor_agent_prompt_smoke2.ipynb` gained exactly one
  markdown cell whose first line is `## Mordor generated: agent smoke`. The
  corresponding operation
  `~/.local/state/mordornotebook/notebook_ops/d5e8bbe8-2b0d-42c9-949c-d82def22d4da.json`
  ended with status `live_applied`.
- Expanded acceptance notebook:
  `notebooks/qa_scratch/mordor_prompt_box_acceptance_20260608T235921Z.ipynb`
  passed the four required prompts below in one browser/kernel session:
  fresh universe load, registered memory slice, recent returns chart with
  `image/png`, and missing-object error transparency with panel `Status:
  Failed`.
- Deterministic fake-agent notebook:
  `notebooks/qa_scratch/mordor_prompt_box_fake_agent_20260608T235921Z.ipynb`
  proved unsupported prompts can travel through the managed-agent operation
  queue and render live notebook cells without relying on a live model.
- Deterministic stalled-agent and cancelled-agent notebooks proved visible
  failure/cancel states:
  `notebooks/qa_scratch/mordor_prompt_box_stall_20260608T235921Z.ipynb` and
  `notebooks/qa_scratch/mordor_prompt_box_cancel_20260608T235921Z.ipynb`.

Automated unit/regression tests:

```bash
<navstrategies-repo>/.venv/bin/python -m pytest tests
```

Result: `26 passed`.

Reusable browser QA harness:

```bash
<navstrategies-repo>/.venv/bin/python scripts/qa_mordor_prompt_box.py \
  --base-url http://127.0.0.1:5011
```

Latest passing artifact:

```text
<navstrategies-repo>/milestones/mordor_prompt_box_qa/20260608T235921Z/summary.json
```

Still open: packaged labextension release mechanics and broader arbitrary
prompt regression coverage beyond the required acceptance prompts.

## Failure Being Corrected

The failed manual workflow was:

1. The user opened `<nav-ui-base-url>/jlab/lab/tree/x123.ipynb`.
2. The user ran:

   ```python
   from mordornotebook import attach

   mordor = attach(
       repo="<navstrategies-repo>",
       goal="manual Mordor smoke",
   )
   mordor.panel()
   ```

3. The panel showed debug buttons:
   - `Context`
   - `Insert Audit`
   - `Start Codex`
   - `Send Prompt`
   - `Capture`
   - `Ops`
4. The user clicked buttons and saw JSON acknowledgements, but no clear running
   state, no clear transcript, and no notebook cells appearing in front of them.
5. The active Mordor session metadata pointed at `Untitled.ipynb` while the
   browser was on `x123.ipynb`, so file-backed operations could target the wrong
   notebook.
6. A cell insert was only visible after leaving/reloading the notebook.

This means the shipped manual panel failed the actual product contract.

## Root Causes

### Wrong Acceptance Standard

The earlier QA accepted durable `.ipynb` mutation plus an automated reload
handshake. That proves a file can eventually be changed. It does not prove a
human can interact with Codex inside a notebook.

The accepted standard must be live visible notebook mutation and execution in
the currently open notebook.

### Debug UI Leaked Into Product UI

The panel exposed internal operations as user actions:

- `Start Codex`
- `Capture`
- `Ops`
- `Insert Audit`

Those are implementation details. They do not map to the user's mental model.
The user's model is: type an instruction, receive notebook work.

### No Current-Notebook Binding

The runtime guessed a notebook path from kernel environment state. In the
observed failure, that produced `Untitled.ipynb` while the browser was viewing
`x123.ipynb`.

The browser is the authority on the notebook the user is looking at. If the
server cannot prove that cell operations target that notebook, it must refuse to
insert or execute cells.

### No Live Cell Application

The current MVP writes notebook JSON on disk when `notebook_path` is available.
JupyterLab does not automatically merge that file change into the active
NotebookPanel. The user therefore sees no cell until reload, and reload can
destroy the sense of live interaction.

The product must apply cells through the active JupyterLab document model, then
save through JupyterLab.

### No Visible Agent Lifecycle

The panel can return `{"ok": true}` from agent start/send without showing:

- whether Codex is already running;
- whether a prompt is queued;
- whether Codex is thinking;
- what Codex is doing;
- whether cells were inserted;
- whether cells are executing;
- whether execution completed or failed.

That makes the UI feel dead even when backend state changed.

## Product Contract

Mordor Notebook is usable only when the following contract holds.

### User-Facing Contract

The notebook panel has one primary action:

```text
Ask Mordor
```

The user types a prompt, presses Send, and the panel visibly moves through:

1. `Queued`
2. `Reading notebook`
3. `Inspecting repo/data`
4. `Writing cells`
5. `Inserting cells`
6. `Running cells`
7. `Done` or `Failed`

The user does not need to know about tmux, capture, ops, cell queues, bridge
ports, or whether Codex was already started.

### Notebook Contract

For each successful prompt:

- one or more generated cells appear in the current open notebook without
  requiring page reload;
- generated cells are complete and self-contained enough to understand;
- code cells are executed in the current kernel unless the prompt or safety
  policy says not to execute;
- outputs render inline in the notebook;
- markdown cells explain what the agent did and what files/data paths it used;
- cell metadata records the Mordor request id, session id, source hash, and
  generated role;
- saving the notebook persists the same cells the user saw.

### Agent Contract

Codex is managed by Mordor. There is no `Start Codex` button.

When the user sends the first prompt, Mordor starts or reuses an auditable tmux
agent automatically. The panel shows a concise status and a transcript tail.

The agent can:

- inspect notebook context;
- inspect registered memory packets;
- inspect the configured repo;
- generate markdown/code cells;
- request live insertion;
- request execution;
- observe execution result summaries;
- continue from the result.

### Safety Contract

Mordor must refuse cell operations when:

- the browser-visible notebook path and server session notebook path disagree;
- the active JupyterLab document cannot be found;
- the active kernel cannot be found;
- live insertion fails and only file mutation is available;
- executing generated code would require an unsafe operation without explicit
  confirmation.

The panel must show a clear failure message instead of silently queueing work or
writing the wrong file.

## New UI Shape

The panel should be rebuilt around the user task.

### Visible UI

```text
Mordor Notebook
Repo: <navstrategies-repo>
Notebook: x123.ipynb
Status: Ready

[ prompt textarea ]
[ Send ]

Activity
- Ready

Generated Cells
- none yet
```

During a run:

```text
Status: Running - inspecting repo/data

Activity
- Prompt sent
- Codex session attached
- Reading x123.ipynb
- Inspecting navstrategies data utilities
- Preparing 2 cells
- Inserted markdown cell
- Inserted code cell
- Running code cell
- Done
```

After a run:

```text
Generated Cells
- Markdown: Equity parquet loading audit
- Code: Load fresh equity universe panel
```

The transcript tail can be visible under an expandable `Agent Log` section, but
it is not the primary control surface.

### Removed UI

The following controls are removed from the product panel:

- `Start Codex`
- `Capture`
- `Ops`
- `Insert Audit`
- raw bridge URL as a prominent user-facing concept
- raw JSON as the normal response view

Developer diagnostics may exist behind a separate debug flag, but they must not
be the default UI.

## Architecture Changes

### 1. Browser-Authoritative Notebook Session

Add a JupyterLab frontend integration that reports the active notebook document
to the Mordor server extension:

```json
{
  "notebook_path": "x123.ipynb",
  "notebook_url": "/jlab/lab/tree/x123.ipynb",
  "kernel_id": "...",
  "session_id": "...",
  "document_id": "..."
}
```

The server stores this as the browser-bound active document for the Mordor
session. The runtime's guessed `notebook_path` is advisory only.

Acceptance rules:

- If the browser says `x123.ipynb`, inserts must target `x123.ipynb`.
- If the runtime says `Untitled.ipynb` but the browser says `x123.ipynb`, the
  browser wins or the operation is blocked.
- The panel displays the resolved notebook path.
- A mismatch is visible and blocks mutation.

### 2. Live JupyterLab Cell Insertion

Implement live insertion through the JupyterLab document model, not by editing
the `.ipynb` file behind JupyterLab's back.

Required behavior:

- insert markdown/code cells into the active NotebookPanel;
- use the NotebookPanel model/shared model so the cell appears immediately;
- tag each cell with Mordor metadata;
- scroll to the inserted cell;
- save through JupyterLab after insertion;
- report inserted cell ids and indices back to the server.

File-backed insertion may remain as a crash-recovery fallback, but it is not a
passing user workflow.

### 3. Live Execution And Render Verification

The frontend must be able to execute inserted code cells in the current kernel.

Required behavior:

- execute generated code cells after insertion when execution is allowed;
- stream status back to the panel;
- detect execution success/failure;
- show traceback/error summaries in the panel;
- verify that the notebook cell has visible output when output is expected;
- save after successful execution.

### 4. Prompt Request State Machine

Create a first-class request model:

```text
created
queued
agent_starting
agent_running
planning
cell_draft_ready
inserting
executing
rendered
complete
failed
cancelled
```

Every request has:

- request id;
- notebook path;
- repo path;
- prompt;
- current status;
- created/started/finished timestamps;
- generated cell manifests;
- execution results;
- redacted transcript path;
- error message if failed.

The panel subscribes to request events. It should not require the user to press
`Capture`.

### 5. Agent Execution Model

Keep tmux as the auditable substrate, but hide it from the product UI.

The reliable first implementation should avoid fragile multiline typing into the
interactive Codex TUI. Instead, Mordor should run one prompt job at a time in a
tmux pane using a deterministic command shape, such as:

```bash
codex exec --cd <navstrategies-repo> -- <prompt-file>
```

The tmux pane remains auditable. Mordor captures stdout/stderr and stores the
transcript. The panel streams the transcript tail and status events.

If an interactive Codex TUI is retained later, it must have a tested submit
path. A prompt sitting unsubmitted in the Codex input box is a hard failure.

### 6. Agent-To-Notebook Operation API

Codex should not write notebook files directly. It should request notebook work
through Mordor commands:

```bash
mordorctl notebook context --json
mordorctl memory list --json
mordorctl repo status --json
mordorctl cell propose --type markdown --file /tmp/mordor/audit.md --json
mordorctl cell propose --type code --file /tmp/mordor/load_panel.py --execute --json
```

`mordorctl cell propose` creates an operation for the frontend to apply live.
The frontend applies it, executes it if requested, and reports completion.

The old direct file mutation path should be renamed to something explicit like:

```bash
mordorctl cell file-insert --unsafe-reload-required
```

It should not be used by the product panel.

## Stage-Gated Implementation Plan

### Stage 0: Stop Calling The Current Panel Usable

Deliverables:

- Update docs to mark the current panel as a debug/development panel.
- Remove "production-ish" language from docs until live UX passes.
- Add this recovery plan to the docs index.

Acceptance:

- Docs no longer tell the user that the current panel is ready for manual
  notebook work.

### Stage 1: Replace The Product Panel UI

Deliverables:

- Replace debug buttons with:
  - prompt textarea;
  - `Send`;
  - `Stop` only when a request is running;
  - status line;
  - activity feed;
  - generated-cell list;
  - expandable agent log.
- Remove `Start Codex`, `Capture`, `Ops`, and `Insert Audit` from the default
  UI.
- Show resolved notebook path and repo path.
- Show a blocking warning if active notebook binding is missing.

Acceptance:

- A Playwright test opens a notebook, renders the panel, and verifies that no
  debug controls appear.
- The only primary workflow is prompt -> send -> visible request status.

### Stage 2: Bind To The Current Notebook

Deliverables:

- Browser panel reports current JupyterLab notebook path to the server.
- Server stores browser-bound notebook path on the active Mordor session.
- Cell operations reject mismatched or missing notebook paths.

Acceptance:

- Browser opened on `x123.ipynb` results in active session path `x123.ipynb`.
- A stale runtime path such as `Untitled.ipynb` does not receive generated
  cells.
- A test intentionally creates a mismatch and verifies mutation is blocked.

### Stage 3: Live Cell Insert

Deliverables:

- JupyterLab frontend applies generated cells through the active NotebookPanel.
- Inserted cells appear without reload.
- Inserted cells are selected/scrolled into view.
- Notebook save persists them.

Acceptance:

- Playwright sends a prompt to a scratch notebook.
- A generated markdown cell appears within the open notebook without reload.
- A generated code cell appears within the open notebook without reload.
- The saved `.ipynb` contains exactly the visible generated cells.
- No cell is written to any other notebook.

### Stage 4: Live Cell Execution

Deliverables:

- Generated code cells execute in the active kernel.
- Outputs render inline.
- Errors surface in the panel and notebook.
- The request state transitions to `complete` only after expected outputs are
  present.

Acceptance:

- A prompt asking for a small DataFrame creates and runs a code cell.
- The DataFrame HTML output is visible without reload.
- A prompt asking for a chart creates and runs a chart cell.
- The chart output is visible without reload.

### Stage 5: Managed Codex Prompt Jobs

Deliverables:

- `Send` starts/reuses the backend agent automatically.
- The agent job is auditable in tmux.
- Prompt submission is deterministic and tested.
- The panel streams status and transcript tail automatically.
- A hung agent becomes visibly `stalled` with a timeout and next action.

Acceptance:

- No user action called `Start Codex` exists.
- No user action called `Capture` exists.
- Sending a prompt produces visible progress within 2 seconds.
- If Codex does not start or submit, the panel says so.
- A prompt never silently sits in a tmux input box.

### Stage 6: End-To-End Product QA

Deliverables:

- A deterministic fake-agent harness for fast CI-style browser tests.
- A live Codex smoke harness for the real tmux/Codex path.
- Artifacts for each run:
  - starting notebook;
  - final notebook;
  - screenshots/video;
  - request event log;
  - transcript;
  - generated cell manifest;
  - pass/fail summary.

Acceptance:

- The exact manual flow is tested by automation:
  1. open `/jlab/lab/tree/x123.ipynb` or a scratch equivalent;
  2. run `attach(...); mordor.panel()`;
  3. type a natural-language prompt;
  4. click `Send`;
  5. observe running status;
  6. observe generated cells appear without reload;
  7. observe code cells execute and outputs render;
  8. save and reopen notebook;
  9. verify cells and outputs persist.
- This test must pass before anyone tells the user to test Mordor Notebook.

## Required Acceptance Prompts

The app is not usable until these prompts pass through the real UI.

### Prompt 1: Fresh Equity Universe Loader

```text
Identify how to load the fresh equity parquet for the equity universe. Add a
short markdown explanation cell and a code cell that loads a small sample and
displays metadata.
```

Required result:

- Markdown cell explains the discovered artifact/function.
- Code cell loads from the fresh parquet/cache path.
- Output displays latest date, row count/sample count, columns, and sample rows.
- Cells appear and execute without reload.

### Prompt 2: In-Memory Object Inspection

```text
Inspect the registered panel object and insert a cell that shows a recent date
slice for three symbols selected from the data.
```

Required result:

- Agent uses Mordor memory/context APIs.
- Symbols are derived from the data, not pasted by the harness.
- Output table renders.

### Prompt 3: Chart

```text
Create a simple chart from the loaded panel that lets me visually inspect recent
returns for a few names.
```

Required result:

- Code cell renders a visible chart inline.
- Panel marks the request complete only after the chart output exists.

### Prompt 4: Error Transparency

```text
Load a deliberately missing object named DOES_NOT_EXIST and show me what failed.
```

Required result:

- The UI does not hang.
- The notebook receives either a clear diagnostic markdown cell or a failed code
  cell with traceback.
- The panel status is `Failed` with a useful message.

## Non-Negotiable Done Standard

Mordor Notebook cannot be called usable until:

- the default UI has no debug buttons;
- the current browser notebook path is authoritative;
- generated cells appear without reload;
- generated code cells execute and render inline;
- prompts show progress automatically;
- tmux/Codex is managed automatically;
- the panel never requires `Capture` to understand what is happening;
- mismatched notebook paths block mutation;
- wrong-file writes are covered by tests;
- the exact manual notebook workflow is covered by Playwright;
- the QA artifacts prove no reload was used as the success mechanism.

## Explicitly Not Good Enough

The following are not acceptable as product evidence:

- JSON acknowledgement from `agent/send`;
- a prompt visible but unsubmitted in the Codex tmux input box;
- file mutation that becomes visible only after reload;
- cells inserted into `Untitled.ipynb` while the browser is on another notebook;
- a passing test that prewrites generated cells;
- a passing test where Playwright reloads the page to observe inserted cells;
- a panel that requires the user to know what `Capture`, `Ops`, or `Insert
  Audit` means.

## Implementation Order

1. Mark current UI as debug only.
2. Replace the UI with prompt/status/activity/generated-cells.
3. Add browser-authoritative notebook binding.
4. Add live JupyterLab cell insertion.
5. Add live execution and render verification.
6. Replace fragile interactive tmux prompt submission with deterministic
   tmux-audited prompt jobs.
7. Add fake-agent browser tests.
8. Add live Codex browser smoke.
9. Update quickstart only after the above passes.

As of the `20260608T235921Z` browser artifact, these nine steps pass for the
local navstrategies JupyterLab gateway. The docs may describe the prompt-box
workflow as locally usable, while still calling out remaining packaged-release
mechanics and broader arbitrary prompt regression coverage.
