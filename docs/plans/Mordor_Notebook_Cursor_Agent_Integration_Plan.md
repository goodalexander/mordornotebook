# Mordor Notebook Cursor Agent Integration Plan

Research date: 2026-06-09.

Implementation update: the initial local Cursor backend, CLI/server backend
selection, doctor probe, and notebook panel selector are implemented. Raw Cursor
NDJSON transcript capture is used for completion detection because tmux pane
wrapping can split `MORDOR_NOTEBOOK_DONE`. Browser QA now proves Cursor inserts
two live notebook cells in one notebook without stale-op false completion:
`<navstrategies-repo>/milestones/mordor_cursor_backend_qa/20260609T031322Z/summary.json`.

## Purpose

Add Cursor Agent as an alternate Mordor Notebook backend while keeping Mordor's
notebook UX contract unchanged:

- The user types a prompt in the Mordor notebook panel.
- The backend agent works against the active repo and active notebook session.
- The only acceptable user-facing result is complete notebook cells rendered in
  the current JupyterLab notebook.
- The user should see live status, generated-cell acknowledgements, and failure
  messages without opening a separate terminal.

Cursor is not the product UI here. Cursor is one possible execution backend
behind Mordor's notebook-native prompt box.

## Current Inputs

Official Cursor docs establish the relevant surfaces:

- Cursor CLI can be installed with `curl https://cursor.com/install -fsS | bash`
  and is positioned for terminal agents, scripts, automations, and CI:
  <https://cursor.com/en-US/cli>
- Cursor Agent CLI supports non-interactive `-p` / `--print` mode for scripts:
  <https://cursor.com/docs/cli/using>
- Cursor CLI exposes structured output with `--output-format` values including
  `json` and `stream-json`: <https://cursor.com/docs/cli/reference/output-format>
- Cursor Agent CLI parameters include auth, model, resume, force/yolo, and print
  options: <https://cursor.com/docs/cli/reference/parameters>
- Cursor background/cloud agents run asynchronously in remote environments and
  have different security and data-retention properties:
  <https://cursor.com/docs/cloud-agent>
- Cursor's data-science guide says Cursor can work with `.ipynb` files inside
  the Cursor IDE when the Jupyter extension is installed, but that path edits an
  IDE notebook document. Mordor still needs its own JupyterLab/kernel bridge
  because the target UX is a live browser notebook with in-memory objects:
  <https://docs.cursor.com/en/guides/advanced/datascience>

Local probe on this server:

```text
cursor-agent path: /home/goodalexander/.local/bin/cursor-agent
cursor-agent version: 2026.05.20-2b5dd59
auth status: logged in
```

The local `cursor-agent --help` output also shows practical options that matter
for Mordor:

```text
--workspace <path>
--trust
--sandbox enabled|disabled
--force / --yolo
--mode plan|ask
--stream-partial-output
--output-format text|json|stream-json
```

Local probe found that `cursor-agent ls` attempts an interactive Ink UI and can
fail in a non-raw stdin process. Server-side Mordor code must avoid Cursor
subcommands that require a live TTY unless they are run inside tmux purely for
human audit capture.

Cursor/Jupyter prior-art check: public Cursor notebook workflows are centered
on opening `.ipynb` files in Cursor/VS Code-style editors. That does not solve
Mordor's hard requirement that the agent create and run cells in the user's
already-open JupyterLab notebook. The implemented integration therefore treats
Cursor as a headless repo agent and routes all notebook mutation through
`mordorctl cell insert`.

## Initial Decision

Implement the first Cursor backend against the local headless CLI, not Cursor
Cloud Agents.

Reason:

- Mordor needs live insertion into the notebook currently open in JupyterLab.
- The existing Codex backend already proves the right contract: agent output is
  useful only when it calls `mordorctl cell insert` and the labextension applies
  those operations live.
- Cursor Cloud Agents work in remote cloned repos and separate branches. That is
  valuable later for offline repo work, but it is not the direct path for
  inserting cells into a live local notebook kernel with in-memory objects.

Cloud/background agents can be a later backend after the local adapter is stable.

## Required Backend Contract

Define a provider-neutral agent interface before wiring Cursor into the panel:

```python
class AgentBackend(Protocol):
    name: str

    def doctor(self) -> dict[str, object]: ...
    def send(self, prompt: str, *, session_name: str) -> dict[str, object]: ...
    def capture(self, *, session_name: str, lines: int = 200) -> dict[str, object]: ...
    def stop(self, *, session_name: str) -> dict[str, object]: ...
```

The interface must preserve the current Codex behavior:

- one request maps to one deterministic agent session name;
- every request has a Mordor request id;
- the agent is prompted to inspect notebook context first;
- the agent must create notebook cells through `mordorctl cell insert`;
- the agent must never edit `.ipynb` files directly;
- the agent must emit `MORDOR_NOTEBOOK_DONE <request_id>` only after cells are
  inserted;
- the panel declares success only after new cell operations for the same request
  are applied or an explicit no-cell answer is rendered as a notebook cell;
- nonzero process exit, timeout, or missing completion marker is visible failure.

## Cursor Command Shape

The target command shape should be explicit rather than relying on Cursor
defaults:

```bash
cursor-agent \
  --print \
  --output-format stream-json \
  --stream-partial-output \
  --workspace /path/to/repo \
  --trust \
  --sandbox disabled \
  --model <configured-model> \
  "$PROMPT"
```

Implementation notes:

- Use `--workspace` instead of shell `cd` assumptions.
- Use `--output-format stream-json` even if local defaults change.
- Keep `--sandbox`, `--force`, and `--yolo` config-gated. Cursor headless mode
  has write and shell access, so defaults must be deliberate.
- Capture stdout, stderr, exit code, Cursor session id, and request id when
  available.
- Parse NDJSON incrementally so the Mordor panel can display meaningful
  activity rather than a generic "working" state.
- Ignore unknown NDJSON fields; Cursor documents the schema as extensible.

## Prompt Contract

Cursor receives the same high-level instruction as Codex, adjusted only for its
CLI:

```text
You are operating inside a live Jupyter notebook through Mordor Notebook.

User prompt: <user prompt>
Request id: <request id>
Repository: <repo>
Use this exact mordorctl binary: <repo>/.venv/bin/mordorctl

Rules:
- Do not edit notebook files directly.
- Do not ask the user to run commands.
- Inspect the active notebook context first with: mordorctl notebook context --json
- Inspect in-kernel memory with: mordorctl memory list --json
- Inspect the repo as needed with rg and normal shell reads.
- Answer by creating complete notebook cells with mordorctl cell insert.
- Insert a markdown audit/summary cell first when useful.
- Insert executable code cells when the user asks for data inspection, charts,
  or calculations.
- Keep generated cells bounded and runnable in the active notebook.
- The first line of every generated cell must include "Mordor generated".
- When all requested cells have been inserted, print:
  MORDOR_NOTEBOOK_DONE <request id>
```

Cursor must be judged by rendered notebook cells, not by a text-only response.

## Stage Gates

### Gate 0: Discovery And Config

Deliverables:

- Add config fields:
  - `agent_backend`: `codex` or `cursor`, default `codex`.
  - `cursor_command`: default `cursor-agent`.
  - `cursor_model`: optional.
  - `cursor_sandbox`: default `disabled` only if this matches the operator's
    trust model; otherwise default `enabled` and document tradeoffs.
  - `cursor_force`: default `true` for the Mordor notebook backend because
    headless Cursor must be able to run `mordorctl` without an approval prompt.
- Extend `mordorctl doctor --json` with Cursor checks:
  - executable path;
  - version;
  - `cursor-agent status --format json` or text fallback;
  - ability to run a headless no-write smoke in `--mode ask`.

Acceptance:

- Doctor reports Cursor as available/unavailable without throwing.
- Missing auth is a clear panel/doctor failure.
- Interactive-only Cursor commands are not used in server request paths.

### Gate 1: Provider Abstraction

Deliverables:

- Move Codex-specific code behind a provider-neutral adapter boundary.
- Keep existing `TmuxAgent` behavior working as `CodexTmuxAgent`.
- Add tests proving the panel can request `codex` or `cursor` by backend name.
- Preserve fake-agent test hooks for deterministic browser QA.

Acceptance:

- Existing Codex tests still pass.
- No UI regression: the user still sees only prompt, status, generated cells,
  stop, and logs.

### Gate 2: Cursor Headless Adapter

Deliverables:

- Add `mordornotebook/agent/cursor.py`.
- Run Cursor as a managed process or inside tmux with a non-interactive command.
- Prefer tmux if we want identical audit-pane behavior; prefer direct subprocess
  if NDJSON streaming is more reliable. Either choice must expose the same
  `capture` and `stop` contract to the panel.
- Write request prompt files and transcript files under
  `~/.local/state/mordornotebook`.
- Parse `stream-json` events:
  - `system` initializes session metadata;
  - `assistant` deltas append to visible activity/log;
  - `tool_call` start/completion events become activity rows;
  - terminal `result` records final text.

Acceptance:

- A direct adapter unit test with a fake `cursor-agent` binary proves command
  construction, NDJSON parsing, nonzero exit failure, and timeout handling.
- No test depends on live Cursor service.

### Gate 3: Local Cursor Smoke

Deliverables:

- Add `scripts/qa_cursor_agent_backend.py`.
- First smoke is read-only:

```bash
cursor-agent --print --mode ask --output-format stream-json \
  --workspace <mordornotebook-repo> \
  --trust \
  "Return exactly: MORDOR_CURSOR_SMOKE"
```

- Second smoke uses a throwaway notebook session and asks Cursor to insert one
  markdown cell through `mordorctl cell insert`.

Acceptance:

- Smoke records artifacts under a navstrategies or mordornotebook milestone
  folder.
- The rendered notebook contains a visible generated cell.
- The panel does not mark success until the operation is `live_applied`.
- Re-running the same prompt twice inserts two fresh cells and does not reuse a
  stale queued operation.

### Gate 4: Panel Backend Selection

Deliverables:

- Add a hidden/localStorage or config-backed backend selector first, not a noisy
  user-facing control.
- Panel request payload includes `backend: "codex" | "cursor"`.
- Activity text says `Cursor agent working` when backend is Cursor.
- Stop kills the correct process/session.

Acceptance:

- Codex remains default.
- Cursor can be enabled per browser or per repo without editing source.
- Wrong backend names fail clearly.

### Gate 5: Browser Regression

Deliverables:

- Extend the Playwright/JupyterLab smoke matrix:
  - open notebook through Mordor menu/toolbar;
  - send a Cursor-backed unsupported prompt;
  - verify live markdown cell insertion;
  - send a second Cursor-backed prompt in the same notebook;
  - verify no false completion;
  - verify timeout/cancel paths;
  - verify notebook reload still shows inserted cells.

Acceptance:

- Browser evidence includes screenshot, notebook path, operation ids, statuses,
  transcript path, and generated cell count.
- Failure screenshots are saved when Cursor does not insert cells.

### Gate 6: Documentation And Runbook

Deliverables:

- Document setup:
  - install Cursor CLI;
  - log in with `cursor-agent login`;
  - verify `cursor-agent status`;
  - configure Mordor backend.
- Document security:
  - Cursor headless can write files and run shell tools;
  - `--force` is the default for the notebook backend because otherwise
    headless Cursor rejects shell commands such as `mordorctl cell insert`;
  - cloud/background agents are not the live-notebook backend.
- Document troubleshooting:
  - auth failure;
  - non-TTY/Ink raw-mode failure;
  - no notebook cells generated;
  - stale queued ops;
  - nonzero Cursor exit.

Acceptance:

- A new user can run the smoke test without reading source.
- Docs state that success means rendered notebook cells, not a successful CLI
  text response.

## Failure Modes To Guard

- Cursor returns a useful text answer but inserts no cells.
- Cursor edits the notebook file directly instead of using `mordorctl`.
- Cursor exits zero but never emits the Mordor done marker.
- Cursor emits old/stale cell operations from a previous request.
- Cursor requires a TTY for a subcommand used by the server.
- Cursor auth expires or is unavailable to the Jupyter server process.
- Cursor writes repo changes during a notebook-only prompt.
- Cursor background/cloud mode creates a remote branch that cannot touch the
  live local notebook kernel.
- Large NDJSON logs overwhelm the panel.
- Stop kills the tmux shell but leaves child processes running.

## Recommended First Implementation Slice

Do not start by adding a visible backend picker. The first implementation should
be:

1. `CursorAgent` adapter with fake-binary tests.
2. `mordorctl doctor` Cursor probe.
3. Config/localStorage backend override.
4. One browser QA script proving Cursor inserts a live markdown cell twice in
   one notebook.
5. Only then expose Cursor as an operator-selectable backend.

This keeps the product contract centered on the notebook while allowing Cursor
to be evaluated as a stronger or complementary agent backend.
