# Mordor Notebook Remote QA Plan

## Purpose

Mordor Notebook is not done when unit tests pass. It is done only when a Codex
driver can operate inside the real navstrategies Jupyter environment through the
same browser/gateway path the user uses, insert cells into live notebooks, render
outputs, inspect registered in-kernel objects, and recover cleanly from failures
without user QA.

This plan is the required backend/gateway QA contract. It is not sufficient by
itself to call Mordor Notebook usable; the usable notebook product standard is
defined in
[Mordor Notebook Usable Product Recovery Plan](Mordor_Notebook_Usable_Product_Recovery_Plan.md).

## Prior QA Failure

A previous QA attempt produced a notebook with pre-authored pandas cells that
loaded a panel, ran a small backtest, and rendered a chart. That was invalid
evidence. It proved that Python/Jupyter can execute hard-coded analysis cells;
it did not prove Mordor Notebook functionality.

That failure must not recur. The central product claim is:

```text
From inside a live notebook, Mordor/Codex can inspect notebook/repo/memory
context, decide what code to add, insert the cells through the notebook bridge,
and produce rendered outputs in the notebook.
```

Any QA artifact where the panel load, backtest, or chart cells were prewritten
in the source notebook before the Mordor/Codex run is disqualified. Such an
artifact may be kept as a data-path smoke test, but it must not be cited as
Mordor Notebook capability evidence.

## Incident Being Guarded Against

Observed failure:

```text
Mordor panel error: TypeError: Failed to fetch
Bridge: http://127.0.0.1:<port>
```

Root failure class:

- The notebook panel rendered browser JavaScript that called the kernel runtime
  bridge directly at `http://127.0.0.1:<port>`.
- When Jupyter is reached through the navstrategies server/gateway, browser
  `127.0.0.1` is the user's local machine, not the server-side kernel host.
- A local kernel bridge can still be used by server-side tools such as
  `mordorctl`, but browser UI must call the Jupyter Server extension through the
  current Jupyter origin/base URL.

Required fix class:

- Notebook-rendered UI must use relative Jupyter Server extension routes, e.g.
  `mordor/api/...` under the current Jupyter base URL.
- The Jupyter Server extension can proxy to the active kernel runtime bridge
  server-side.
- Browser-facing HTML must not require direct access to kernel-local
  `127.0.0.1` ports.

## Non-Negotiable Done Standard

Do not mark a Mordor Notebook task done until all of the following pass:

1. Package tests pass.
2. Jupyter Server extension is enabled in the navstrategies `.venv`.
3. The real navstrategies gateway path works:
   `<nav-ui-base-url>/app?tab=notebooks` -> Jupyter -> notebook panel.
4. Browser-side Mordor panel controls call Jupyter-relative APIs, not raw
   `127.0.0.1:<kernel-bridge-port>`.
5. A Codex driver can start, receive a prompt, and capture output from the panel.
6. A Codex driver can inspect notebook context and registered memory packets via
   `mordorctl`.
7. The starting evidence notebook is a thin bootstrap notebook only: attach
   Mordor, optionally register one tiny seed object, and state the task. It must
   not contain the panel load, backtest, chart, or final audit cells before the
   Mordor/Codex run.
8. A Codex driver can use `mordorctl` and repo inspection to discover the
   correct navstrategies data loading path; hard-coded pasted analysis from the
   QA author does not count.
9. A Codex driver can insert markdown and code cells through Mordor into the
   target notebook, with exactly one saved notebook cell per insert. The browser
   verifier may use an automated reload handshake to observe file-backed
   insertion, but a runtime-side `applied_live: true` response is not evidence
   by itself.
10. The inserted cells load the existing hot stock/ETF panel, run a bounded
    backtest, and render a chart.
11. Inserted code cells execute and their table/chart outputs render in the live
    notebook.
12. The QA run saves artifacts: starting notebook, final notebook, screenshots,
    API responses, tmux transcript, inserted-cell manifest, and a pass/fail JSON
    summary.

## QA Harness Shape

Create a deterministic harness under Mordor Notebook:

```text
tests/remote_navstrategies/
  conftest.py
  test_panel_remote_gateway.py
  test_cell_insert_rendering.py
  test_legacy_notebook_driver_matrix.py
scripts/
  qa_navstrategies_remote.py
  qa_navstrategies_agent_generated_notebook.py
```

The harness must support:

- `--base-url http://127.0.0.1:5011` for local server-side execution.
- `--base-url <nav-ui-base-url>` for the same route exposed to the user.
- `--password-env NAV_UI_PASSWORD` with default fallback only in local dev.
- `--jupyter-base /jlab/`.
- `--artifact-dir milestones/mordor_remote_qa/<timestamp>/`.
- `--no-destructive`: copy notebooks into a QA scratch directory before edits.

Required tools:

- `pytest` for Python contract tests.
- Playwright for browser tests against the actual gateway.
- `nbformat` for creating/copying QA notebooks.
- `jupyter_server` extension API checks.
- `mordorctl` for Codex-driver-side memory/context/cell operations.
- A transcript verifier that proves the inserted analysis cells came from the
  Mordor/Codex driver, not from pre-authored notebook source.

## Stage Gates

### Acceptance Hierarchy

The stage gates are not equal.

- Gates 0-3 are plumbing gates. They prove the server extension, browser route,
  panel API, tmux launch, and primitive cell-insertion mechanics work. Passing
  them alone must never be described as Mordor Notebook being usable.
- Gate 3A is the first product acceptance gate. It proves the actual user
  claim: Codex can operate from inside a live notebook, inspect context, use
  repo knowledge, author notebook cells, insert them through Mordor, and leave
  rendered evidence in the notebook.
- Gates 4-5 are supporting contracts consumed by Gate 3A. Registered memory and
  fresh universe loading only count when the Gate 3A driver uses them from the
  live notebook flow.
- The legacy notebook matrix is regression coverage after Gate 3A passes. It is
  not a substitute for Gate 3A.

### Gate 0: Environment Contract

Validate before opening a browser:

- `python -c "import mordornotebook; print(mordornotebook.__version__)"`
- `mordorctl doctor --json`
- `jupyter server extension list` shows `mordornotebook` enabled.
- `GET /jlab/mordor/api/health` through the navstrategies gateway returns JSON.
- Active Jupyter server uses navstrategies `.venv`.
- Active notebook directory is `<navstrategies-repo>/notebooks`.

Failure rule:

- If the extension is not visible through `/jlab/mordor/api/health`, stop. Do
  not proceed to notebook QA.

### Gate 1: Browser Panel Contract

Open a scratch notebook through the gateway and execute:

```python
from mordornotebook import attach

mordor = attach(
    repo="<navstrategies-repo>",
    goal="remote QA smoke",
)
mordor.panel()
```

Assertions:

- Panel renders "Mordor Notebook".
- Panel shows the repo path.
- Browser console has no `Failed to fetch`.
- Network calls go to `/jlab/mordor/api/...`.
- Rendered panel JavaScript does not call `fetch("http://127.0.0.1`.
- Legacy debug controls, if present, return structured output or a clear
  server-side error. These controls are not the accepted product UI.

Failure rule:

- Any browser fetch to a kernel-local bridge URL fails the gate.

### Gate 2: Server Proxy Contract

From the browser route and from Python requests, verify:

- `GET /jlab/mordor/api/health`
- `GET /jlab/mordor/api/notebook/context`
- `GET /jlab/mordor/api/memory`
- `POST /jlab/mordor/api/notebook/cell`
- `POST /jlab/mordor/api/agent/start`
- `POST /jlab/mordor/api/agent/send`
- `GET /jlab/mordor/api/agent/capture`

Assertions:

- All endpoints return JSON.
- Auth/session failures are explicit HTTP errors, not browser `TypeError`.
- Server extension can read active session metadata and proxy to the runtime
  bridge from server-side Python.

### Gate 3: Primitive Live Cell Insertion Smoke

This is a non-acceptance smoke test. It may use toy data because it is only
testing the bridge primitive: a live notebook can receive a cell, execute it,
render output, save, and reopen. It does not prove the Mordor Notebook product
claim and must not be cited as evidence that Codex can do financial notebook
work.

This gate must verify the notebook document, not only the runtime return value.
The sequence only passes if Playwright sees the cells in JupyterLab, the saved
notebook contains the inserted source, and reopening the notebook still shows
the cells and outputs.

In a scratch notebook, use the panel and `mordorctl` to insert:

1. Markdown cell:

```markdown
## Mordor QA Audit
```

2. Code cell:

```python
import pandas as pd
pd.DataFrame({"ticker": ["QA1", "QA2"], "value": [1, 2]})
```

3. Chart cell:

```python
import pandas as pd
import matplotlib.pyplot as plt

s = pd.Series([1.0, 1.1, 1.05, 1.25], index=pd.date_range("2026-01-01", periods=4))
s.plot(title="Mordor QA Equity Curve")
plt.show()
```

Assertions:

- Cells appear in the notebook after the automated browser verification
  handshake. A file-backed insert may require an automated reload because the
  current implementation does not include a JupyterLab frontend document plugin.
- Code cell executes.
- DataFrame HTML table renders.
- Matplotlib output renders.
- Notebook save persists inserted cells.
- Reopening the scratch notebook shows the inserted cells and outputs.
- The final notebook contains exactly one generated cell for each requested
  insert. Duplicate generated cells fail the gate.

Failure rule:

- Queueing without durable notebook mutation, writing a static pass artifact
  outside Mordor, or requiring a human manual reload does not pass.
- Delivering the same source through both notebook-file insertion and
  `IPython.set_next_input` does not pass. That creates duplicate cells and
  invalidates the evidence.
- Treating `applied_live: true` from `IPython.set_next_input` as sufficient
  evidence does not pass. That flag only means the runtime attempted a frontend
  insertion. It does not prove JupyterLab accepted, displayed, saved, or
  executed the inserted cell.

### Gate 3A: Agent-Generated Notebook Contract

This is the primary acceptance gate. It supersedes any pre-authored demo
notebook.

Gate 3A has three separate subgates. All three must pass in the same run:

1. Agent generation: Codex inspects live notebook context, memory, and repo
   state, discovers the data path, authors generated cell sources, and calls
   `mordorctl cell insert`.
2. Notebook insertion: the generated cells appear in the live JupyterLab
   notebook and are saved into the `.ipynb` file. `applied_live: true` alone is
   not credited.
3. Notebook execution: the saved generated code cells execute in the notebook
   kernel and leave rendered table/chart outputs in the final notebook artifact.

Starting state:

- Create a scratch notebook under
  `<navstrategies-repo>/notebooks/qa_scratch/`.
- The source notebook may contain only:
  - a markdown title describing the QA objective;
  - one attach/bootstrap code cell;
  - optional tiny seed object registration used only to prove memory plumbing.
- The source notebook must not contain:
  - imports from `navstrategies.utilities.hot_universe`;
  - `load_hot_universe`;
  - `cache_status`;
  - `pivot`;
  - `rank`;
  - `long_mask`, `short_mask`, `weights`, `strategy_return`;
  - `matplotlib`, `plt`, `.plot(`, or chart code;
  - ticker lists such as `["AAPL", "NVDA", "SOXL", "KORU"]`;
  - hard-coded universe or backtest formulas beyond the natural-language task.

Required prompt sent to Codex through Mordor:

```text
You are operating inside a live navstrategies Jupyter notebook through Mordor.
Use mordorctl to inspect notebook context, repo status, and memory. Then insert
notebook cells that:
1. discover the existing navstrategies hot universe/data-update loading path;
2. load the fresh stock/ETF panel from the existing parquet/cache path without
   cold-scanning raw CSV;
3. display cache metadata and a latest-date sample;
4. run a small bounded, lagged backtest suitable only for QA;
5. render a chart in the notebook;
6. register the loaded panel and backtest outputs with Mordor if needed.

Do not assume the user has hand-authored these cells. Insert the cells through
Mordor so the notebook itself becomes the audit artifact.
```

Prompt boundary:

- The harness prompt may describe the business task, the required evidence, and
  the commands Codex must use.
- The harness prompt must not contain ready-to-run panel-load, backtest, or chart
  source code.
- The harness prompt must not contain a pasted ticker list or a pasted
  implementation of the strategy. Codex must derive any sample symbols from the
  loaded data or from repo/context inspection and record that choice in the
  transcript.
- Codex may create temporary cell-source files under `/tmp` only as an
  implementation detail before calling `mordorctl cell insert --file ...`.

Actor separation:

| Actor | Allowed | Forbidden |
|---|---|---|
| QA harness | Create the thin starting notebook, open JupyterLab, execute the bootstrap cell, start Codex, send the natural-language prompt, execute inserted cells after Codex adds them, save the notebook, capture screenshots/transcripts/API payloads, and verify artifacts. | Author, prewrite, or insert the panel-load/backtest/chart cells; call `load_hot_universe`; compute the backtest; create the chart; modify the final notebook file directly to make it pass. |
| Codex driver inside tmux | Use `mordorctl`, shell repo inspection, and notebook context to discover the right loading path; author generated cell source; call `mordorctl cell insert` for each generated cell; print a completion marker. | Rely on cells already present in the source notebook; write a static notebook artifact directly instead of inserting cells through Mordor; skip `mordorctl` context/memory/repo inspection. |
| Notebook kernel | Execute the generated cells and render outputs. | Hide failures by loading unrelated cached objects or silently falling back to cold raw CSV scans. |

Required transcript evidence:

- `mordorctl notebook context` appears in the tmux transcript.
- `mordorctl memory list` or `mordorctl memory inspect` appears in the
  transcript.
- `mordorctl repo status` or `mordorctl repo diff` appears in the transcript.
- At least one repo/data discovery command appears, for example `rg` over
  `navstrategies.utilities.hot_universe`, `manage_intraday_research_cache`, or
  related data-update modules.
- `mordorctl cell insert` appears for:
  - one markdown audit section;
  - one panel-load cell;
  - one backtest cell;
  - one chart/render cell.
- The transcript includes enough generated code or referenced cell manifest IDs
  to connect the inserted notebook cells to the driver run.

Required notebook evidence:

- Final notebook has more cells than the starting notebook.
- Inserted cells are visibly marked with a generated header such as
  `# Mordor generated`.
- The final notebook contains exactly four generated cells: one audit cell, one
  panel-load cell, one backtest cell, and one chart/render cell. Extra generated
  cells or duplicate generated roles fail the gate.
- The inserted-cell manifest records cell index, cell type, first-line marker,
  SHA-256 source hash, and the transcript command that inserted it.
- A panel metadata table renders.
- A latest-date panel sample renders.
- A bounded backtest summary renders.
- A chart output renders.
- The final notebook is saved to the QA artifact directory.

Failure rules:

- If the source scratch notebook already contains the panel/backtest/chart code,
  the gate fails.
- If the final notebook contains rendered outputs but the transcript does not
  prove Codex/Mordor inserted the relevant cells, the gate fails.
- If a human or setup script inserts the analysis cells directly, the gate fails.
- If the QA harness contains ready-to-run source strings for the panel-load,
  backtest, or chart cells outside denylist validation, the gate fails.
- If the driver only creates a static notebook file on disk and does not insert
  cells through the live notebook/Mordor bridge, the gate fails.
- If the QA harness cannot distinguish pre-authored cells from driver-inserted
  cells, the gate fails.
- If a single requested insert creates duplicate notebook cells, the gate fails.

Current known Gate 3A state:

- Run `20260608T204145Z` proved the agent-generation subgate only and exposed
  that `applied_live: true` from `IPython.set_next_input` was not sufficient
  evidence of notebook mutation.
- Run `20260608T213031Z` exposed a second regression class:
  `mordorctl cell insert` was delivering the same source through both
  notebook-file mutation and `IPython.set_next_input`, producing duplicate
  generated notebook cells. That artifact is a failure artifact and must not be
  cited as a matrix pass.
- The runtime now treats notebook-file insertion as the authoritative delivery
  path when `notebook_path` is configured. In that mode, `mordorctl cell insert`
  returns `persisted_notebook: true`, `applied_live: false`, and skips
  `IPython.set_next_input` to prevent duplicate cells.
- Run `20260608T215431Z` is the current clean Gate 3A pass after the
  duplicate-cell fix and stricter verifier:
  `<navstrategies-repo>/milestones/mordor_remote_qa/20260608T215431Z/summary.json`.
- The current passing run proves:
  - Codex ran in tmux through Mordor and inspected notebook context, memory, and
    repo state.
  - Codex discovered the existing stock/ETF parquet/cache path from repo
    inspection.
  - Codex authored the generated cells under `/tmp` and inserted them through
    `mordorctl cell insert`.
  - The generated cells persisted into the scratch notebook, became visible in
    JupyterLab after the harness reload handshake, executed, and rendered
    metadata/sample/backtest/chart outputs.
- The verifier now fails unless the final notebook contains exactly four
  generated cells: one audit cell, one panel-load cell, one backtest cell, and
  one chart/render cell.

### Gate 4: Registered Memory Contract

In the notebook kernel:

```python
import pandas as pd
from mordornotebook import attach

panel = pd.DataFrame(
    {
        "ticker": ["QA1", "QA2", "QA3"],
        "trade_date": pd.to_datetime(["2026-06-05"] * 3),
        "close": [201.0, 144.0, 470.0],
    }
)
mordor = attach(repo="<navstrategies-repo>", goal="memory QA")
mordor.register("panel", panel)
mordor.panel()
```

Assertions:

- Panel memory endpoint lists `panel`.
- `mordorctl memory list --json` lists `panel`.
- `mordorctl memory inspect panel --head 2 --json` returns bounded rows.
- Context packet includes memory summaries without dumping full frames.

### Gate 5: Fresh Universe Loader Contract

This gate validates the notebook workflow for navstrategies stock/ETF universes
without cold-scanning the old M06 CSV.

The loader cell must be inserted by the Mordor/Codex driver during Gate 3A. The
plan intentionally does not prescribe source code for that cell. The driver must
discover the stable navstrategies hot-universe utility or documented artifact
from repo inspection, then author the notebook cell itself.

Assertions:

- Load uses the hot parquet cache, not
  `milestones/M06_fmp_sharadar_concat/canonical_equity_etf_overlap_ohlcv.csv`.
- The driver discovered this path from repo inspection or documented local
  utilities; it did not receive a pasted hard-coded implementation from the QA
  author.
- Metadata is displayed in a markdown or DataFrame cell.
- `panel` is registered and inspectable by Mordor.
- A date slice cell renders:

```python
latest_date = panel["trade_date"].max()
panel.loc[panel["trade_date"].eq(latest_date)].head(20)
```

- Any ticker slice must derive its symbols from the loaded panel or from a
  transcript-recorded repo/context inspection. The starting notebook, harness,
  and prompt must not provide a preselected ticker list as an acceptance crutch.

Failure rule:

- If hot cache is stale or missing, the harness reports that explicitly and
  stops. It must not silently run a cold rebuild during QA.

## Legacy Notebook Driver Matrix

Each legacy notebook must be copied into a scratch QA directory before testing.
The driver may run a bounded subset of cells, but it must prove that Mordor can
inspect context, insert audit cells, execute rendering cells, and save outputs.

| Notebook | Required Mordor Driver Actions | Required Render Proof |
|---|---|---|
| `00_malaal_universe_data.ipynb` | Load/register hot universe panel; inspect latest date and symbol counts. | DataFrame of latest stock/ETF universe rows. |
| `01_peering_index_peer_set.ipynb` | Inspect peer/index objects or insert loader cell if absent. | Peer set table and one index comparison chart. |
| `02_peering_basket_peer_set.ipynb` | Inspect basket peer definitions and insert audit summary. | Basket peer table. |
| `03_drift_backtest_audit.ipynb` | Register backtest panel/equity curve when present; insert drift audit. | PnL/equity curve chart and top rows table. |
| `04_tradeable_universe_last5y.ipynb` | Load hot universe; insert date/ticker slice audit. | Latest universe table. |
| `05_earnings_event_audit.ipynb` | Inspect earnings/event objects or insert bounded SEC event loader. | Event-window table. |
| `06_tradeable_universe_last5y_with_earnings.ipynb` | Join/slice universe plus earnings events. | Joined ticker/event table. |
| `07_tradeable_universe_last5y_with_index_peer_context.ipynb` | Inspect index and peer context columns. | Ticker vs index/peer returns table or chart. |
| `08_sf1_fcf_yield_ev_sanity_check.ipynb` | Inspect SF1/EV/FCF frame; insert sanity audit. | FCF yield sample table and chart. |
| `09_sf1_fcf_yield_rank_backtest_pandas.ipynb` | Inspect rank/backtest objects; insert bounded PnL audit. | Rank sample table and PnL chart. |
| `10_sf1_garp_matrix_cache.ipynb` | Inspect matrix cache metadata and registered matrices. | Matrix shape table and sample rows. |
| `11_sf1_basic_daily_multiindex.ipynb` | Validate MultiIndex slicing through Mordor helper. | Date/ticker MultiIndex slice table. |
| `M05_wikipedia_trends_explorer.ipynb` | Inspect trend panels and insert sample page/ticker audit. | Trend time series chart. |
| `M06_fmp_sharadar_concat_demo.ipynb` | Validate stock/ETF overlap load path without cold scan. | Overlap sample table. |
| `M27_sec_earnings_release_history_demo.ipynb` | Inspect SEC history artifact and insert ticker audit. | Recent filings table with links where available. |
| `M27_sec_earnings_release_history_examples.ipynb` | Run bounded examples through Mordor inserted cells. | Example output table. |

Pass criteria per notebook:

- Mordor panel loads.
- `Context` works.
- Exactly one generated markdown audit cell is inserted and saved.
- Exactly one generated code/render cell is inserted, saved, and executed.
- No duplicate generated cells exist in the final notebook.
- At least one visible table or chart output renders.
- Notebook is saved to the artifact directory.
- Screenshot is captured after render.
- Driver summary records pass/fail with error details.

Current known matrix state:

- Run `20260608T222027Z` is the current clean legacy matrix pass:
  `<navstrategies-repo>/milestones/mordor_remote_qa/20260608T222027Z/summary.json`.
- The run passed all 16 listed notebooks.
- Every notebook inserted exactly one generated markdown audit cell and exactly
  one generated code/render cell.
- Every insert used durable notebook-file mutation with
  `persisted_notebook: true` and `applied_live: false`.
- The verifier found no duplicate generated sources and no raw browser requests
  to the kernel-local runtime bridge.
- Every final notebook rendered at least one table and chart output before the
  screenshot/final-notebook artifact was saved.

## Codex Driver Contract

The QA driver must exercise the backend agent path behind the notebook UI:

1. Ensure the Codex-backed Mordor agent is running without exposing a user-facing
   start button.
2. Send a prompt that asks Codex to inspect the active notebook and registered
   memory.
3. Require Codex to use `mordorctl notebook context`.
4. Require Codex to use `mordorctl memory list`.
5. Require Codex to inspect the navstrategies repo to discover data-loading
   utilities and existing artifacts.
6. Require Codex to insert a markdown audit section.
7. Require Codex to insert the panel-load, bounded-backtest, and chart cells.
8. Execute the inserted cells in the notebook.
9. Save the tmux transcript artifact and verify the expected `mordorctl` calls
   appear.
10. Verify the final notebook contains rendered outputs from inserted cells.

The transcript is part of the QA artifact. A hidden passing unit test is not
enough.

The driver must not be credited for work if the QA harness already authored the
analysis cells. A notebook with a prewritten backtest is a fixture, not proof of
Mordor Notebook functionality.

## Browser Automation Contract

Playwright must capture:

- Initial JupyterLab page load.
- Scratch notebook open.
- Attach cell execution.
- Mordor panel visible.
- Each panel button response.
- Inserted cell visible.
- Executed output visible.
- Final screenshot per notebook.

Playwright must fail the run on:

- Browser console `Failed to fetch`.
- Network request to `http://127.0.0.1:<dynamic-port>` from page JavaScript.
- Unhandled promise rejection.
- Jupyter modal errors.
- Notebook dirty state after save attempt.

## Artifact Layout

Each QA run writes:

```text
milestones/mordor_remote_qa/<YYYYMMDDTHHMMSSZ>/
  summary.json
  summary.md
  environment.json
  browser_console.jsonl
  network_requests.jsonl
  starting_notebook.ipynb
  final_notebook.ipynb
  inserted_cells_manifest.json
  screenshots/
  notebooks/
  api/
  tmux/
```

`summary.json` schema:

```json
{
  "ok": false,
  "base_url": "...",
  "jupyter_base": "/jlab/",
  "mordor_version": "...",
  "navstrategies_repo": "<navstrategies-repo>",
  "gates": {
    "environment": "pass|fail",
    "browser_panel": "pass|fail",
    "server_proxy": "pass|fail",
    "cell_insertion": "pass|fail",
    "memory": "pass|fail",
    "agent_generation": "pass|fail",
    "notebook_insertion": "pass|fail",
    "notebook_execution": "pass|fail",
    "agent_generated_notebook": "pass|fail",
    "fresh_universe": "pass|fail",
    "legacy_matrix": "pass|fail"
  },
  "agent_generated_notebook": {
    "starting_notebook": "starting_notebook.ipynb",
    "final_notebook": "final_notebook.ipynb",
    "transcript": "tmux/mordor-navstrategies.log",
    "inserted_cells_manifest": "inserted_cells_manifest.json",
    "rendered_outputs": {
      "metadata_table": true,
      "latest_sample": true,
      "backtest_summary": true,
      "chart": true
    }
  },
  "legacy_notebooks": [
    {
      "path": "notebooks/legacy/00_malaal_universe_data.ipynb",
      "status": "pass|fail|skipped",
      "error": null,
      "screenshot": "screenshots/..."
    }
  ]
}
```

## Implementation Order

### Stage A: Close The Browser Bridge Regression

Work:

- Route every browser panel action through Jupyter-relative
  `/jlab/mordor/api/...` endpoints.
- Proxy server-side from the Jupyter extension to the active kernel runtime
  bridge where needed.
- Add unit tests that render panel HTML and assert no browser-facing direct
  `127.0.0.1:<bridge-port>` fetch is present.

Pass artifact:

- Package test output.
- Browser/API smoke summary proving the navstrategies gateway reaches
  `/jlab/mordor/api/health`, `/notebook/context`, `/memory`, `/agent/*`, and
  `/notebook/cell`.

### Stage B: Prove Primitive Live Insertion

Work:

- Open a scratch notebook through the real navstrategies notebook tab.
- Execute only an attach/bootstrap cell.
- Use Mordor panel or `mordorctl` to insert toy markdown/code/chart cells.
- Execute, render, save, reopen, and screenshot.

Pass artifact:

- `jupyterlab_live_panel.json`
- `jupyterlab_live_panel.png`

Acceptance note:

- This is still plumbing evidence only. It cannot close the project.

### Stage C: Build Gate 3A Harness

Work:

- Add `scripts/qa_navstrategies_agent_generated_notebook.py`.
- The script creates a thin starting notebook and copies it to
  `starting_notebook.ipynb` before Codex starts.
- The script launches Codex in a clean tmux session through Mordor.
- The script sends a natural-language prompt that requires Codex to use
  `mordorctl notebook context`, `mordorctl memory list`, repo inspection, and
  `mordorctl cell insert`.
- The script waits for a completion marker, captures the tmux transcript, then
  executes the Codex-inserted cells in JupyterLab.
- The script saves `final_notebook.ipynb`, screenshots, network/console logs,
  and `inserted_cells_manifest.json`.
- The script separately records:
  - agent-generation evidence;
  - browser-visible inserted-cell count;
  - saved-notebook inserted-cell count;
  - rendered output evidence.

Harness restrictions:

- The script may contain denylist validation terms, but it must not contain
  ready-to-run panel-load, backtest, or chart cell bodies.
- The script must fail if the starting notebook contains forbidden analysis
  code.
- The script must fail if the transcript does not prove the generated cells came
  from Codex/Mordor cell insertion.
- The script must fail if `applied_live: true` appears in the transcript but the
  generated cells are absent from the live browser or saved notebook.

Pass artifact:

- `summary.json` with `gates.agent_generation = "pass"`,
  `gates.notebook_insertion = "pass"`,
  `gates.notebook_execution = "pass"`, and
  `gates.agent_generated_notebook = "pass"`.
- `inserted_cells_manifest.json` with generated cell hashes and transcript
  insertion references.
- `tmux/<session>.log` containing context, memory, repo inspection, and cell
  insertion commands.
- `final_notebook.ipynb` containing rendered metadata, latest sample, backtest
  summary, and chart outputs.

### Stage D: Replace Optimistic Cell Insertion With Verified Notebook Mutation

Work:

- Audit the current insertion path and treat `IPython.set_next_input` as an
  optimistic transport only.
- Implement a JupyterLab-compatible insertion path that mutates the active
  notebook document, or a server-extension path that uses Jupyter contents/
  session metadata plus a frontend refresh/command handshake that Playwright can
  verify.
- The insertion API must return separate fields for attempted runtime delivery,
  browser-visible insertion, and saved-notebook persistence.
- The QA harness must reject any run where generated cells are not present in
  both the browser and final saved `.ipynb`.

Pass artifact:

- Primitive Gate 3 run where inserted cells are visible, saved, reopened, and
  rendered.
- Gate 3A run where the four generated cells survive browser save/reopen before
  any execution evidence is credited.

### Stage E: Wire Fresh Universe Into Gate 3A

Work:

- Require the Codex driver to discover the hot stock/ETF parquet/cache path from
  navstrategies repo inspection.
- Require the generated loader cell to display cache metadata and latest-date
  samples.
- Require the generated loader cell to register the loaded panel with Mordor.
- Reject cold scans of legacy raw CSV artifacts.

Pass artifact:

- The Gate 3A transcript shows repo discovery of the loader path.
- The final notebook shows fresh cache metadata and latest-date panel rows.
- `mordorctl memory inspect` can inspect the registered panel in bounded form.

### Stage F: Legacy Notebook Matrix

Work:

- Copy each legacy notebook to a scratch QA path.
- Have Codex/Mordor insert a live audit cell and one bounded render cell.
- Save screenshots and pass/fail summaries per notebook.

Pass artifact:

- `legacy_notebooks[]` entries in `summary.json` with screenshots and error
  details.

### Stage G: Publish Status

Work:

- Sync the docs suite.
- Update `docs/Implementation_Status.md` with the latest passing Gate 3A
  artifact path only after Stage C, Stage D, and Stage E pass in one run.

Pass artifact:

- Docs build/sync output.
- Implementation status explicitly names what passed and what remains unproven.

## Stop Rules

Stop and report immediately if:

- The gateway route cannot reach Jupyter.
- The Mordor server extension is not loaded in the active Jupyter process.
- Any browser panel call fails with `TypeError: Failed to fetch`.
- Cell insertion only queues to disk and does not appear in the live notebook.
- `mordorctl cell insert` reports `applied_live: true` but Playwright cannot
  find the generated cells in the live JupyterLab notebook within the timeout.
- The generated cells appear in the browser but are absent from the saved
  `.ipynb` after `Control+S` and reopen.
- The QA starts from a notebook that already contains the analysis/backtest/chart
  code that Mordor is supposed to generate.
- The transcript does not prove `mordorctl` context/memory/repo inspection and
  cell insertion were used.
- A notebook test needs a cold raw CSV scan to proceed.
- Codex starts but cannot use `mordorctl` to inspect context.

Do not ask the user to validate these conditions manually. The QA harness must
produce screenshots, API payloads, and transcript artifacts.
