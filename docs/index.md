# Mordor Notebook

Mordor Notebook puts a local coding agent inside the JupyterLab workflow. A user
opens a notebook, clicks `Mordor`, types a request, and the selected backend
generates notebook cells through Mordor's notebook API.

## User Documentation

- [Install A Fresh Instance](Install.md)
- [Architecture](Architecture.md)
- [Codex And Cursor Backends](Agent_Backends.md)
- [Current Status](Status.md)
- [Helper Workspace](Mordor_Helper_Workspace.md)
- [Legacy OpenRouter Helper](legacy/Legacy_OpenRouter_Helper.md)

## Planning Archive

The plan documents are retained because they explain why the product changed,
what was tested, and what still needs more QA. They are not the starting point
for users.

- [Plan Status Index](plans/index.md)
- [Detailed Implementation Evidence Log](Implementation_Status.md)

## One-Screen Summary

```text
JupyterLab button
  -> silently runs attach(...) in the active kernel
  -> runtime bridge exposes notebook memory on 127.0.0.1
  -> Jupyter Server extension proxies authenticated browser requests
  -> panel sends prompt to Codex or Cursor via tmux
  -> agent uses mordorctl cell insert
  -> JupyterLab extension inserts and renders cells in the open notebook
```

Codex is the default backend. Cursor Agent is optional and uses the same cell
insertion contract.
