# Mordor Helper Workspace

Mordor creates a small repo-local helper workspace for any repo it is attached
to. The point is to keep notebooks readable: agents should put reusable logic in
helper modules, then insert short notebook cells that import and call those
helpers.

## Layout

```text
<repo>/
  mordor/
    HELPERS.md
    helpers.json
    .gitignore
    cache/
    tmp/
    runs/
  mordorhelper/
    __init__.py
    catalog.py
```

`mordor/helpers.json` is the helper manifest. Every reusable helper should have
a plain-English description, import path, call shape, inputs, and outputs.

`mordorhelper/` is the importable Python package. Agents should add small,
accessible helper modules here rather than pasting large analysis code into the
notebook.

## Git Behavior

Mordor does not ignore all helper code by default. Helper source and
`mordor/helpers.json` are meant to be reusable and can be committed when they
become part of the repo workflow.

The default gitignore only covers runtime artifacts:

```text
/mordor/cache/
/mordor/tmp/
/mordor/runs/
/mordor/*.log
/mordor/**/*.pyc
/mordor/**/__pycache__/
```

## Agent Contract

Before writing notebook code, the agent is instructed to run:

```bash
mordorctl helpers ensure --json
mordorctl helpers list --json
```

Then it should:

- reuse an existing helper if one fits;
- create or update a small helper under `mordorhelper/` if no helper fits;
- update `mordor/helpers.json` when adding helper behavior;
- keep notebook cells thin.

The preferred notebook shape is:

```python
# Mordor generated
from mordorhelper.wikipull.trends import TrendManager

requested_term = "requested search term"
report = TrendManager().get(requested_term)
display(report.summary)
display(report.latest_rows)
report.show()
```

The helper should hold the date handling, API access, plotting defaults, and
formatting logic. The notebook cell should hold the request-specific term and
display calls.

## Manual Commands

Prepare a repo:

```bash
cd /path/to/repo
mordorctl helpers ensure --json
```

List registered helpers:

```bash
mordorctl helpers list --json
```
