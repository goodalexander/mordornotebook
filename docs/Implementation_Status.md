# Mordor Notebook Implementation Status

## Current Product Status

The current implementation has crossed the core prompt-to-live-cell threshold:
from a notebook, a user can render `mordor.panel()`, type into one prompt box,
click `Send`, and receive generated cells in the currently open JupyterLab
notebook without a page reload.

Two paths are now verified:

- a local notebook-aware handler for the fresh navstrategies equity universe
  parquet prompt, including code execution and rendered DataFrame outputs;
- a hidden tmux/Codex fallback for an unsupported prompt, where Codex calls
  `mordorctl cell insert`, Mordor queues a browser-bound cell operation, the
  labextension applies it live, and the operation is acknowledged as
  `live_applied`.

The required acceptance prompts in the recovery plan are verified in a single
browser/kernel session: fresh universe load, registered memory slice, chart
rendering, and missing-object error transparency. The browser harness also now
verifies deterministic fake-agent insertion, visible stalled-agent timeout, and
request cancellation. Remaining product hardening is packaged release mechanics
and broader arbitrary prompt regression coverage. The accepted target remains
[Mordor Notebook Usable Product Recovery Plan](plans/Mordor_Notebook_Usable_Product_Recovery_Plan.md).

## Implemented

- `mordorctl` console command.
- Safe config/state directories:
  - `~/.config/mordornotebook`
  - `~/.local/state/mordornotebook`
- `mordorctl doctor` with Codex, tmux, Jupyter, writable-dir, and redacted
  Jupyter-config secret checks.
- `from mordornotebook import attach`.
- In-kernel runtime bridge started by `attach(...)`.
- Named memory packets with bounded DataFrame/Series/Path/basic-object
  summaries.
- `mordorctl memory list`.
- `mordorctl memory inspect`.
- `mordorctl notebook context`.
- Durable cell operation queue.
- `mordorctl cell insert`.
- Fallback cell delivery through IPython `set_next_input` only when no
  `notebook_path` is configured.
- Queue fallback when live insertion is unavailable.
- `mordorctl visual pnl`.
- `mordorctl memory slice`.
- `mordorctl visual event-window`.
- `mordorctl repo status`.
- `mordorctl repo diff`.
- tmux/Codex adapter:
  - `mordorctl agent start`
  - `mordorctl agent send`
  - `mordorctl agent capture`
  - startup prompt handling for Codex update/trust prompts
- Jupyter Server extension endpoints for health, session, context, ops, live
  cell insertion proxy, memory proxy, agent controls, and repo status.
- `mordorctl jupyter enable --sys-prefix` for deterministic Jupyter Server
  extension config in editable installs.
- `mordor.panel()` injected product panel with prompt textarea, `Send`,
  a running-only `Stop` control, status, activity, generated-cell list, visible
  stalled/timeout/cancel states, and expandable agent log. The default panel no
  longer exposes `Start Codex`, `Capture`, `Ops`, or `Insert Audit`.
- Prebuilt JupyterLab labextension source/bundle that exposes
  `window.mordorNotebookLab`, reports the active notebook, inserts cells through
  the active `NotebookPanel`, executes code cells, exposes a reliable
  `runActiveCell()` QA hook, and saves through JupyterLab.
- JupyterLab `Mordor` top-menu entry and notebook toolbar button. The action
  silently attaches in the active kernel and renders the prompt panel without
  inserting a bootstrap cell, preserving an existing `mordor` object when
  present.
- Browser-authoritative notebook binding via `/mordor/api/session`.
- Browser-bound `mordorctl cell insert` queues live cell operations instead of
  mutating the `.ipynb` file behind JupyterLab. File-backed insert remains only
  a fallback when no browser notebook is bound.
- Hidden per-request tmux/Codex fallback from the `Send` button. The panel
  starts/sends/captures internally and applies queued notebook operations live.
- Managed fallback now runs `codex exec` inside a per-request tmux session
  instead of pasting prompt text into the interactive Codex TUI. This keeps the
  tmux audit trail while avoiding the `[Pasted Content ...]` non-submission
  failure mode.
- Agent backend selector in the notebook panel with `Codex` and `Cursor`
  choices. The panel keeps one user workflow for both: prompt, visible status,
  generated cells, stop, and agent log.
- Cursor Agent backend plumbing:
  - config fields for backend, command, model, sandbox, and force mode;
  - `mordorctl agent ... --backend cursor`;
  - Jupyter Server `/agent/send`, `/agent/capture`, and `/agent/stop` backend
    selection;
  - tmux-backed headless `cursor-agent --print --output-format stream-json`
    execution with raw NDJSON transcript capture;
  - `mordorctl doctor --json` Cursor executable and auth probe.
- Deterministic fake-agent server path for browser QA of agent-created cells,
  stalled requests, and cancellation without relying on a live model.
- Legacy OpenRouter helper path marked deprecated.

## Verified

The repo-local venv was created with:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[notebook,test]'
```

Passing gates:

```bash
<navstrategies-repo>/.venv/bin/python -m pytest tests
.venv/bin/mordorctl doctor --json
.venv/bin/mordorctl jupyter enable --sys-prefix
.venv/bin/jupyter server extension list
.venv/bin/python -m mordornotebook.smoke
.venv/bin/python -m compileall mordornotebook tests
git diff --check
```

Latest unit/regression result:

```text
26 passed
```

Current unit/regression result:

```text
35 passed
```

Cursor backend smoke evidence:

```text
cursor-agent --print --mode ask --output-format json --workspace <mordornotebook-repo> --trust "Return exactly: MORDOR_CURSOR_SMOKE"
```

returned `MORDOR_CURSOR_SMOKE` with exit code `0`.

The tmux-backed Mordor Cursor path was also smoke-tested with:

```text
mordorctl agent send --backend cursor --session mordor-cursor-smoke-20260609 --cursor-command "cursor-agent --mode ask" --cursor-sandbox disabled --text "Do not write files. Return exactly: MORDOR_NOTEBOOK_DONE cursor-smoke-20260609" --json
mordorctl agent capture --backend cursor --session mordor-cursor-smoke-20260609 --json
```

Capture contained the unwrapped marker
`MORDOR_NOTEBOOK_DONE cursor-smoke-20260609` and
`MORDOR_AGENT_EXIT_CODE=0`. This validates headless Cursor execution through
Mordor's agent transport.

Current Cursor browser QA artifact:

```text
<navstrategies-repo>/milestones/mordor_cursor_backend_qa/20260609T031322Z/summary.json
```

Verified behavior:

- the visible panel selector exposed both `Codex` and `Cursor`;
- the selector was set to `Cursor`;
- two unsupported prompts fell through to the managed Cursor backend;
- Cursor inserted two live markdown notebook cells through Mordor;
- both generated cells were visible and saved in the notebook.

Current Codex regression browser QA artifact:

```text
<navstrategies-repo>/milestones/mordor_repeated_codex_fallback_qa/20260609T031424Z/summary.json
```

Verified behavior:

- default `Codex` backend still works with the new selector present;
- two unsupported prompts fell through to managed Codex;
- both generated cells were visible and saved in the notebook.

Latest prompt-box browser smokes:

```text
<navstrategies-repo>/notebooks/qa_scratch/mordor_usable_product_smoke_after_agent_wiring.ipynb
<navstrategies-repo>/notebooks/qa_scratch/mordor_agent_prompt_smoke2.ipynb
```

Reusable prompt-box QA harness:

```bash
<navstrategies-repo>/.venv/bin/python scripts/qa_mordor_prompt_box.py \
  --base-url http://127.0.0.1:5011
```

Latest passing artifact:

```text
<navstrategies-repo>/milestones/mordor_prompt_box_qa/20260608T235921Z/summary.json
```

Verified behavior:

- Fresh equity universe prompt inserted two cells without reload:
  markdown audit + executed code loader.
- The code output rendered inline and showed `latest_trade_date = 2026-06-08`,
  `rows_loaded = 8204322`, and `symbols = 7645`.
- Generic unsupported prompt fell back to hidden Codex and inserted one
  markdown cell headed `## Mordor generated: agent smoke`.
- Operation
  `~/.local/state/mordornotebook/notebook_ops/d5e8bbe8-2b0d-42c9-949c-d82def22d4da.json`
  ended as `live_applied`.
- Active browser metadata persisted the correct notebook path and post-insert
  cell count.
- Expanded acceptance notebook
  `<navstrategies-repo>/notebooks/qa_scratch/mordor_prompt_box_acceptance_20260608T235921Z.ipynb`
  passed:
  - fresh equity universe load with rendered metadata/sample output;
  - registered panel memory slice with symbols selected from data;
  - recent returns chart with saved `image/png` output;
  - missing object diagnostic for `DOES_NOT_EXIST` with panel `Status: Failed`
    and a saved notebook `error` output.
- Deterministic fake-agent notebook
  `<navstrategies-repo>/notebooks/qa_scratch/mordor_prompt_box_fake_agent_20260608T235921Z.ipynb`
  passed the agent-created-cell path without using a live model.
- Deterministic stalled-agent case showed panel `Status: Failed`, a visible
  "No new notebook cells or agent output" activity entry, and a timeout message.
- Deterministic cancel case showed panel `Status: Cancelled` and left the
  notebook without generated cells.
- JupyterLab menu/toolbar access smoke passed:
  `<navstrategies-repo>/milestones/mordor_menu_button_qa/20260609T015439Z/summary.json`.
  It clicked the `Mordor` notebook toolbar button, opened the panel without a
  visible bootstrap cell, submitted the fresh universe prompt, and verified
  `latest_trade_date` plus the generated audit/loader cells.
- Repeated real-Codex fallback smoke passed:
  `<navstrategies-repo>/milestones/mordor_repeated_codex_fallback_qa/20260609T022133Z/summary.json`.
  It sent two unsupported prompts in one notebook and verified two visible
  generated markdown cells, covering the stale-complete/pasted-content failure
  mode.

Partial remote navstrategies QA gates:

```bash
<navstrategies-repo>/.venv/bin/python \
  scripts/qa_navstrategies_remote.py \
  --base-url http://127.0.0.1:5011 \
  --start-agent
```

Partial passing artifact:

```text
<navstrategies-repo>/milestones/mordor_remote_qa/20260608T183237Z/summary.json
<navstrategies-repo>/milestones/mordor_remote_qa/20260608T183237Z/browser_smoke.json
<navstrategies-repo>/milestones/mordor_remote_qa/20260608T183237Z/jupyterlab_live_panel.json
<navstrategies-repo>/milestones/mordor_remote_qa/20260608T183237Z/jupyterlab_live_panel.png
```

That run verified plumbing and file-backed cell mechanics only:

- panel markup does not direct browser `fetch(...)` calls to
  `http://127.0.0.1:<runtime-bridge-port>`;
- navstrategies hot universe parquet cache is fresh through `2026-06-08`;
- `/jlab/mordor/api/health` is live through the navstrategies gateway;
- Jupyter Server extension can proxy memory/context/repo calls to an active
  runtime bridge;
- `agent/start` works through the Jupyter Server extension and captures the
  `mordor-navstrategies` tmux/Codex session;
- browser-side fetches from the JupyterLab page origin can reach health,
  memory, and context through `/jlab/mordor/api/...`, see registered memory, and
  do not make raw `127.0.0.1:<runtime-bridge-port>` requests;
- JupyterLab can run a scratch notebook cell that calls `mordor.panel()`, route
  debug panel requests through the server extension, receive
  `"persisted_notebook": true`, and verify the inserted cell after an automated
  browser reload handshake. This is backend/debug evidence only, not usable
  product evidence;

Invalidated evidence:

- `notebooks/mordor_navstrategies_example.ipynb` contains pre-authored panel
  load, bounded backtest, and chart-render cells. It is useful only as a
  data-path smoke fixture. It must not be cited as proof that Mordor/Codex can
  generate the notebook workflow.

Regression evidence:

- The legacy notebook matrix in
  `docs/plans/Mordor_Notebook_Remote_QA_Plan.md` now passes across the listed
  older notebooks. It is regression coverage for the insertion/render contract;
  Gate 3A remains the product acceptance proof.

Latest Gate 3A passing artifact:

```text
<navstrategies-repo>/milestones/mordor_remote_qa/20260608T215431Z/summary.json
```

That run passed:

- `agent_generation`
- `notebook_insertion`
- `notebook_execution`
- `fresh_universe`
- `agent_generated_notebook`

Evidence in that run:

- Starting notebook was a two-cell bootstrap.
- Codex inspected notebook context, memory, repo status, and repo data paths
  from tmux.
- Codex generated audit, panel-load, bounded-backtest, and chart-render cell
  sources under `/tmp`.
- All four generated cells were inserted through `mordorctl cell insert`.
- The harness verified saved-notebook persistence, browser visibility after the
  reload handshake, and rendered metadata/sample/backtest/chart outputs. The
  reload requirement is a product gap, not acceptable final UX.
- The final notebook contained exactly four generated cells: audit, panel-load,
  bounded-backtest, and chart/render.

Earlier failing artifact `20260608T204145Z` remains useful as the regression
case that proved `applied_live: true` alone was not sufficient evidence.

Failure artifact `20260608T213031Z` exposed a second regression class:
notebook-path inserts were also calling `IPython.set_next_input`, creating a
duplicate Jupyter-generated cell in addition to the Mordor file-backed cell.
The runtime now skips `set_next_input` when `notebook_path` is configured, and
the QA verifier fails duplicate generated cells.

Latest legacy notebook matrix passing artifact:

```text
<navstrategies-repo>/milestones/mordor_remote_qa/20260608T222027Z/summary.json
```

That run passed all 16 legacy notebooks in the matrix. Each notebook ended with
exactly one generated markdown audit cell and one generated code/render cell,
with `persisted_notebook: true`, `applied_live: false`, zero duplicate generated
sources, no raw bridge browser requests, and rendered table/chart evidence.

Additional manual checks:

```bash
.venv/bin/mordorctl memory list --json
.venv/bin/ipython -c "from mordornotebook import attach; s=attach(repo='.', goal='cell-gate'); print(s.insert_cell('code', '1 + 1')); s.stop_bridge()"
codex --help
.venv/bin/mordorctl agent start --json
.venv/bin/mordorctl agent capture --json
```

A real Jupyter kernel was also started with `jupyter_client`; it ran
`attach(...)`, registered a DataFrame named `panel`, and external
`mordorctl memory list --json` saw `panel`.

## Known Gaps

- The UI is still rendered by `mordor.panel()` inside a notebook output. The
  labextension exists, but the user-facing panel is not yet a packaged
  side-panel/launcher experience.
- The active Jupyter server must be restarted after enabling or changing the
  Mordor Jupyter Server extension. The navstrategies Jupyter server was
  restarted on `2026-06-08` and logs `Mordor Notebook server extension loaded`.
- The live JupyterLab QA run still observed non-fatal WebSocket console errors
  from pre-existing kernel/session channels through the gateway. Mordor panel
  actions completed despite those errors, but the gateway WebSocket noise should
  be cleaned up separately.
- The hidden Codex path is proven for a simple markdown-cell prompt. Timeout,
  cancellation, stalled-agent recovery, and broader arbitrary prompt regression
  coverage still need hardening.
- The older Gate 3A and legacy matrix artifacts remain useful regression
  coverage, but their reload/file-backed success mechanism is no longer the
  product standard.
