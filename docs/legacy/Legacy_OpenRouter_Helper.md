# Legacy OpenRouter Helper

## Status

Deprecated.

This repo currently contains an older helper that reads a notebook from disk,
exports selected repositories into a prompt, calls OpenRouter models, and inserts
generated code with `IPython.set_next_input`.

That approach is useful historical context, but it is not the Mordor Notebook
MVP architecture.

## Deprecated Components

- `mordornotebook.wrangling.jupyter_tool.UserQuery`
- `mordornotebook.wrangling.repo_export`
- `mordornotebook.ai.openrouter.OpenRouterTool`
- `mordornotebook.settings.cred_reader`
- `mordornotebook.settings.repo_paths`
- `mordornotebook.settings.global_vars`

## Why It Is Deprecated

- It mutates `jupyter_notebook_config.py` for app-specific state.
- It historically stored or read credential material from Jupyter config.
- It reads notebooks from disk instead of the live JupyterLab notebook model.
- It can miss unsaved notebook state.
- It depends on whole-repo prompt exports instead of bounded, redacted context
  packets.
- It inserts next-cell text but cannot reliably apply structured notebook edits
  or track operation status.
- It does not provide an auditable tmux/Codex transcript inside Jupyter.

## Migration Target

New work should target:

- `from mordornotebook import attach`
- `mordor.register("name", obj)` for in-kernel memory packets
- `mordorctl notebook context`
- `mordorctl memory list/inspect/slice`
- `mordorctl cell insert`
- Jupyter Server extension state under `~/.local/state/mordornotebook`
- safe config under `~/.config/mordornotebook`
- JupyterLab side panel for tmux/Codex transcript and prompt entry

## Retention Policy

Keep the legacy modules only long enough to migrate useful ideas:

- model backend wrappers;
- repo file filtering;
- rough notebook-context formatting.

Do not extend the legacy helper API. If old notebooks still need it, quarantine
it under a clearly marked legacy path or keep compatibility wrappers with
deprecation warnings.
