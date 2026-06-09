# Mordor Notebook Representative QA Goal

## Goal

Build and run a representative Mordor Notebook QA matrix that proves the product
works for real research workflows without the user acting as QA.

The output of this goal is not a demo notebook. The output is an auditable QA
artifact set:

- eight generated notebooks covering materially different navstrategies-style
  research tasks;
- each notebook generated through Mordor from a thin scratch notebook, not
  pre-authored analysis cells;
- each notebook run once with Codex and once with Cursor, for sixteen agent
  runs total;
- saved notebooks with rendered outputs;
- screenshots, transcripts, notebook manifests, and a machine-readable summary;
- a final markdown report that states pass/fail for each agent and use case.

## Non-Negotiable Caveats

Mordor Notebook must not contain hard-coded product logic for this QA.

1. No hard-coded repo references in the app.

   The app, panel, JupyterLab extension, and agent bridge must not bake in a
   single repository path such as a local navstrategies checkout. Repo identity
   must come from the active session, explicit config, environment, or user
   selection. Test fixtures may point at a repo under test, but app code cannot.

2. No hard-coded prompt keywords or domain routers in the app.

   The app must not inspect natural-language prompts for terms like a data
   source name, asset class, notebook topic, or command intent and then inject
   canned notebook cells. Scenario prompts are test inputs only. The selected
   agent must inspect the notebook/repo and decide what cells to create.

3. No prewritten analysis cells.

   Starter notebooks may contain only a minimal bootstrap or seed data required
   to open Mordor. The actual audit, loading, calculation, and chart cells must
   be created by the selected agent through Mordor cell insertion.

4. No fake pass based on panel status alone.

   A run passes only when the saved notebook contains the generated cells,
   executable cells ran successfully, and expected tables/charts/text outputs
   are visible in the notebook artifact.

## Representative Notebook Matrix

Create eight scratch notebooks under the repo-under-test notebook scratch area.
Use generated names with timestamp, scenario id, and backend, for example:

```text
notebooks/qa_scratch/mordor_representative_qa/<timestamp>/<scenario>_<backend>.ipynb
```

The exact repo root must be discovered from the active Mordor session/config,
not hard-coded in app code.

### 1. Wikimedia Pageview Pull

Prompt shape:

```text
Use the repo's Wikimedia helper or source client to pull daily pageview history
for a named public figure or company, summarize latest coverage, and chart the
series.
```

Acceptance:

- agent discovers the helper/client from the repo;
- notebook displays a summary table and latest rows;
- notebook renders a chart image;
- generated code does not use local cache/SQL unless the prompt explicitly asks
  for cache comparison.

### 2. Fresh Equity Panel Load

Prompt shape:

```text
Find the current efficient Parquet-based equity/ETF panel loader, load a bounded
fresh sample, and display coverage, columns, dates, and a few liquid symbols.
```

Acceptance:

- no CSV fallback unless the repo documents it as current;
- notebook displays row counts, date range, symbol count, and sample rows;
- generated code uses discovered repo helpers or documented artifacts;
- loaded object is registered in Mordor memory when useful.

### 3. Sharadar SEP / Daily Liquidity Slice

Prompt shape:

```text
Using the repo's current Sharadar SEP/daily panel artifacts, compute a bounded
liquidity slice and show median dollar volume coverage for recent dates.
```

Acceptance:

- agent discovers current artifact locations from repo/docs/code;
- notebook displays coverage by date and sample tickers;
- output includes enough provenance to know which artifact was loaded;
- no SQL path.

### 4. SEC Extraction / Filing Provenance

Prompt shape:

```text
Inspect the repo's SEC extraction pipeline artifacts and show recent filing
provenance for a small set of tickers, including source accession/index/document
links when available.
```

Acceptance:

- notebook identifies the current SEC artifact/cache path from repo code/docs;
- output distinguishes feed, accession, filing index page, primary document,
  exhibits, parse state, and extraction state where available;
- output includes timestamps/freshness fields;
- missing data is reported explicitly, not swallowed.

### 5. FMP Transcript Coverage

Prompt shape:

```text
Find the repo's FMP transcript storage/access path, inspect recent transcript
coverage for a small ticker set, and display date, quarter/year, and body
availability.
```

Acceptance:

- notebook uses the repo's documented FMP access pattern;
- output shows transcript metadata and clear availability status;
- endpoint/local mismatches are reported as mismatches, not stale data unless
  proven;
- no DeepSeek summarization is required for this scenario unless transcripts
  are already cached and bounded.

### 6. FRED Macro Series Chart

Prompt shape:

```text
Use the repo's FRED access pattern to pull a small set of macro series and chart
them with current/latest values and source series ids.
```

Acceptance:

- agent discovers API-key handling or existing helper code;
- notebook displays series ids, latest dates, latest values, and chart;
- inflation/rate transformations are stated explicitly;
- failures from missing credentials are visible and actionable.

### 7. Cross-Sectional Screen / TBPN-Style Prep

Prompt shape:

```text
Using current panel artifacts, build a bounded cross-sectional screen with
market-cap change and dollar-volume style features, rank or z-score them, and
display the top rows with names.
```

Acceptance:

- agent discovers the current tickers/name-labeling source from repo code/docs;
- notebook explains feature definitions and lookback dates;
- output table has ticker, name, sector if available, feature values, and rank;
- no SQL path unless explicitly documented as the only current source.

### 8. Simple Backtest / Event Window Inspection

Prompt shape:

```text
Using a bounded subset of the current panel data, create a simple inspectable
signal or event-window check, display assumptions, and render a PnL or event
chart.
```

Acceptance:

- generated code is bounded for runtime and memory;
- assumptions and no-lookahead constraints are displayed;
- notebook shows summary metrics and a chart;
- the run is reproducible from the generated cells.

## Backend Matrix

Each scenario must run with both managed backends:

```text
codex
cursor
```

For each backend/scenario pair:

- start from a fresh scratch notebook;
- open through the real JupyterLab/Mordor UI path;
- select the backend in the panel or set it through documented config;
- send the scenario prompt;
- wait for the agent to insert cells through Mordor;
- execute generated code cells in the notebook;
- save the notebook;
- capture transcript and screenshot;
- validate saved notebook contents with `nbformat`.

## Validation Rules

A run passes only if all required checks pass:

- panel reaches `Done`;
- no unhandled JavaScript/browser errors;
- no generated code cell has an error output;
- at least one markdown cell and one code cell are inserted by Mordor;
- code cells have non-empty outputs appropriate to the scenario;
- charts expected by the scenario have `image/png` or equivalent rendered output;
- generated cells include source/provenance where the scenario requires it;
- generated cells are not duplicated by reload/retry artifacts;
- transcript shows the agent used Mordor cell insertion, not direct notebook
  file mutation;
- app source and compiled bundle remain clean of hard-coded repo paths and
  prompt-keyword/domain routers.

## Required Artifact Layout

Write all artifacts under a timestamped milestone directory in the repo under
test or in an explicit artifact directory supplied to the harness:

```text
milestones/mordor_representative_qa/<timestamp>/
  summary.json
  report.md
  source_grep.txt
  notebooks/
    <scenario>_<backend>_start.ipynb
    <scenario>_<backend>_final.ipynb
  screenshots/
    <scenario>_<backend>.png
  transcripts/
    <scenario>_<backend>.log
  manifests/
    <scenario>_<backend>.json
```

`summary.json` must include:

- timestamp;
- repo root under test;
- Mordor package path/version;
- Jupyter base URL;
- backend;
- scenario;
- notebook path;
- generated cell count;
- code output count;
- chart output count;
- error output count;
- pass/fail;
- failure reason.

## Stage Gates

### Gate 0: Source Invariant Audit

Before any notebook run:

- grep app source and compiled bundle for known hard-coded repo paths;
- grep app source and compiled bundle for prompt-router functions/strings;
- fail immediately if app code contains canned natural-language dispatch.

This gate is required because representative QA is invalid if Mordor is
secretly injecting scenario-specific cells.

### Gate 1: Environment And Server Health

Verify:

- Jupyter server is running through the target base URL;
- Mordor Jupyter server extension health endpoint returns JSON;
- JupyterLab extension is loaded in the browser;
- repo root is supplied by active session/config/env;
- both `codex` and `cursor` commands are available or failures are recorded
  before scenario execution.

### Gate 2: Scenario Scaffold

Create the eight starter notebooks. Starter notebooks may contain only:

- a title/metadata cell;
- optional `from mordornotebook import attach` bootstrap if needed;
- no analysis code for the target scenario.

Save copies as `_start.ipynb`.

### Gate 3: Codex Matrix

Run all eight scenarios with Codex. Record every pass/fail. Do not skip failed
scenarios silently.

### Gate 4: Cursor Matrix

Run all eight scenarios with Cursor. Cursor must run with the documented
non-interactive permissions required for notebook operation. If Cursor rejects
shell or tool calls, record the rejection and fix the backend before calling the
matrix complete.

### Gate 5: Notebook Artifact Verification

Use `nbformat`, screenshots, and transcript parsing to verify final notebooks.
Do not trust panel JSON alone.

### Gate 6: Final Report

Write `report.md` with:

- matrix table by scenario/backend;
- links to notebooks/screenshots/transcripts/manifests;
- failures and root causes;
- source invariant audit results;
- exact commands used to run the harness;
- follow-up fixes, if any.

## Implementation Notes

The harness should be generic and scenario-driven:

- scenario definitions live in a data file or Python structure used only by the
  QA harness;
- scenario definitions are not imported by the product UI/runtime;
- scenario prompts may mention data sources, but product code must not branch on
  those words;
- notebook validation may be scenario-specific because validation is test code,
  not app behavior;
- all repo paths in generated notebooks should derive from the active Mordor
  session, environment, config, or notebook metadata.

## Done Definition

This goal is complete only when:

- the source invariant audit passes;
- sixteen backend/scenario notebook runs have completed or failed with explicit
  recorded reasons;
- every passing run has a saved final notebook with rendered outputs;
- `summary.json` and `report.md` exist and are internally consistent;
- no run depends on canned app-side prompt handling;
- no run requires the user to manually inspect or repair the notebook.
