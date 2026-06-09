# Current Status

This page separates product state from planning notes.

## Implemented

| Area | Status |
| --- | --- |
| Python package | Implemented. `mordornotebook` exposes `attach(...)` and installs `mordorctl`. |
| Runtime bridge | Implemented. `attach(...)` starts a localhost bridge inside the active kernel and stores active session metadata. |
| Jupyter Server extension | Implemented. `/mordor/api/...` endpoints proxy panel, memory, context, cell, repo, and agent requests. |
| JupyterLab extension | Implemented. Adds `Mordor` menu/toolbar entry, silently attaches to the kernel, renders the panel, inserts cells, runs code cells, and saves the notebook. |
| Codex backend | Implemented. Managed prompt-box path uses tmux plus `codex exec`. |
| Cursor backend | Implemented as an alternate backend. Uses tmux plus `cursor-agent --print --output-format stream-json`. |
| Cell operation queue | Implemented. Browser-bound operations are queued and then applied by the labextension to the open notebook. |
| In-memory object registry | Implemented. `mordor.register(...)`, `mordorctl memory list`, and `mordorctl memory inspect` are available. |
| Helper workspace | Implemented. Mordor creates `mordor/` and `mordorhelper/` in attached repos and instructs agents to reuse helpers. |
| Doctor checks | Implemented. `mordorctl doctor --json` checks key executable/config/auth surfaces. |

## Verified

The current test suite passes:

```bash
.venv/bin/python -m pytest -q
```

At the time this page was updated, the suite result was `42 passed`.

The detailed evidence log is [Implementation Status](Implementation_Status.md).
That file includes historical QA artifacts and should be read as evidence, not
as the primary user guide.

## Not Yet Final

These areas are still not considered final product polish:

- Packaged release flow beyond editable install from source.
- Broader browser-level regression coverage across many arbitrary notebook
  research prompts.
- More durable UX around long-running agents, cancellation, and transcript
  inspection.
- Full cleanup of deprecated OpenRouter modules. They remain only for migration
  and legacy notebook inspection.

## Plan Documents

The plan files are not all "open work." Some are historical implementation
plans, some are QA plans, and some contain remaining gaps. Use
[Plan Status Index](plans/index.md) to interpret them.
