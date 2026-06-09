"""Repo-local helper workspace support for Mordor Notebook."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

MORDOR_DIR = "mordor"
HELPER_PACKAGE = "mordorhelper"
REGISTRY_FILE = "helpers.json"
RULES_FILE = "HELPERS.md"

ROOT_GITIGNORE_MARKER = "# Mordor Notebook helper workspace"
ROOT_GITIGNORE_LINES = [
    ROOT_GITIGNORE_MARKER,
    "/mordor/cache/",
    "/mordor/tmp/",
    "/mordor/runs/",
    "/mordor/*.log",
    "/mordor/**/*.pyc",
    "/mordor/**/__pycache__/",
]

LOCAL_GITIGNORE = """# Runtime-only Mordor artifacts.
# Helper source, helpers.json, and HELPERS.md are intentionally trackable.
cache/
tmp/
runs/
*.log
*.pyc
__pycache__/
"""

HELPERS_MD = """# Mordor Helper Workspace

This repo-local workspace is where Mordor agents should put reusable notebook
helper code instead of pasting large one-off code blocks into notebooks.

Default contract:

- check `mordor/helpers.json` before writing new helper code;
- reuse an existing helper when the request fits one;
- add small, accessible helper modules under `mordorhelper/` when new reusable
  behavior is needed;
- update `mordor/helpers.json` with a plain-English description, import path,
  call shape, inputs, and outputs for each helper;
- keep notebooks thin: import a helper, call it with request-specific
  parameters, and display the returned tables/charts.

Runtime caches and scratch output belong under `mordor/cache/`, `mordor/tmp/`,
or `mordor/runs/`; those paths are ignored by default.
"""

CATALOG_SOURCE = '''"""Read the repo-local Mordor helper registry.

This module is intentionally dependency-light so helper discovery works in any
repo where Mordor creates the default helper workspace.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class HelperCatalog:
    """Load and query `mordor/helpers.json` from the current repo."""

    def __init__(self, repo_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).expanduser().resolve() if repo_root else self._discover_repo_root()
        self.registry_path = self.repo_root / "mordor" / "helpers.json"

    def _discover_repo_root(self) -> Path:
        here = Path.cwd().resolve()
        for candidate in [here, *here.parents]:
            if (candidate / "mordor" / "helpers.json").exists():
                return candidate
        module_root = Path(__file__).resolve().parents[1]
        if (module_root / "mordor" / "helpers.json").exists():
            return module_root
        for candidate in [here, *here.parents]:
            if (candidate / ".git").exists():
                return candidate
        return here

    def load(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return {"version": 1, "helpers": []}
        return json.loads(self.registry_path.read_text(encoding="utf-8"))

    def list(self) -> list[dict[str, Any]]:
        payload = self.load()
        helpers = payload.get("helpers", [])
        return helpers if isinstance(helpers, list) else []

    def find(self, text: str) -> list[dict[str, Any]]:
        needle = str(text or "").lower()
        if not needle:
            return self.list()
        matches = []
        for helper in self.list():
            haystack = " ".join(
                str(helper.get(key, ""))
                for key in ("id", "description", "import_path", "call", "domain")
            ).lower()
            if needle in haystack:
                matches.append(helper)
        return matches
'''


def _repo_path(repo: str | Path | None) -> Path:
    if not repo:
        raise ValueError("repo is required for Mordor helper workspace operations")
    return Path(repo).expanduser().resolve()


def _default_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "metadata_dir": MORDOR_DIR,
        "helper_package": HELPER_PACKAGE,
        "policy": {
            "check_before_writing_code": True,
            "prefer_helper_calls_over_inline_notebook_code": True,
            "plain_english_descriptions_required": True,
            "runtime_artifacts_are_ignored": ["mordor/cache/", "mordor/tmp/", "mordor/runs/"],
        },
        "helpers": [
            {
                "id": "helper_catalog",
                "domain": "mordor",
                "import_path": "mordorhelper.catalog.HelperCatalog",
                "call": "HelperCatalog().list()",
                "description": (
                    "Reads the repo-local Mordor helper manifest so agents and "
                    "notebooks can discover existing helper functions before "
                    "creating new code."
                ),
                "inputs": [{"name": "repo_root", "description": "Optional repo root path."}],
                "outputs": [{"name": "helpers", "description": "List of helper metadata dictionaries."}],
            }
        ],
    }


def _read_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return raw


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _merge_default_helper(registry: dict[str, Any]) -> bool:
    default_helper = _default_registry()["helpers"][0]
    helpers = registry.setdefault("helpers", [])
    if not isinstance(helpers, list):
        registry["helpers"] = helpers = []
    if any(isinstance(row, dict) and row.get("id") == default_helper["id"] for row in helpers):
        return False
    helpers.insert(0, default_helper)
    return True


def _append_root_gitignore(repo: Path) -> bool:
    path = repo / ".gitignore"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if ROOT_GITIGNORE_MARKER in existing:
        return False
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    path.write_text(existing + prefix + "\n".join(ROOT_GITIGNORE_LINES) + "\n", encoding="utf-8")
    return True


def helper_workspace_status(repo: str | Path | None) -> dict[str, Any]:
    if not repo:
        return {"available": False, "reason": "No repo configured"}
    root = _repo_path(repo)
    registry_path = root / MORDOR_DIR / REGISTRY_FILE
    registry: dict[str, Any] | None = None
    error: str | None = None
    if registry_path.exists():
        try:
            registry = _read_json(registry_path)
        except Exception as exc:
            error = str(exc)
    return {
        "available": registry is not None and error is None,
        "repo": str(root),
        "metadata_dir": str(root / MORDOR_DIR),
        "registry_path": str(registry_path),
        "rules_path": str(root / MORDOR_DIR / RULES_FILE),
        "helper_package_dir": str(root / HELPER_PACKAGE),
        "helper_count": len(registry.get("helpers", [])) if registry else 0,
        "registry": registry,
        "error": error,
    }


def ensure_helper_workspace(
    repo: str | Path | None,
    *,
    update_root_gitignore: bool = True,
) -> dict[str, Any]:
    """Create the repo-local Mordor helper workspace if it is missing.

    The default is deliberately conservative: reusable helper source and the
    registry remain trackable, while cache/tmp/run artifacts are ignored.
    Existing helper files are not overwritten.
    """
    root = _repo_path(repo)
    created: list[str] = []
    updated: list[str] = []
    errors: list[str] = []

    mordor_dir = root / MORDOR_DIR
    helper_pkg = root / HELPER_PACKAGE
    mordor_dir.mkdir(parents=True, exist_ok=True)
    helper_pkg.mkdir(parents=True, exist_ok=True)

    local_gitignore = mordor_dir / ".gitignore"
    if not local_gitignore.exists():
        local_gitignore.write_text(LOCAL_GITIGNORE, encoding="utf-8")
        created.append(str(local_gitignore))

    rules_path = mordor_dir / RULES_FILE
    if not rules_path.exists():
        rules_path.write_text(HELPERS_MD, encoding="utf-8")
        created.append(str(rules_path))

    package_init = helper_pkg / "__init__.py"
    if not package_init.exists():
        package_init.write_text(
            '"""Repo-local helpers created for Mordor Notebook workflows."""\n',
            encoding="utf-8",
        )
        created.append(str(package_init))

    catalog_path = helper_pkg / "catalog.py"
    if not catalog_path.exists():
        catalog_path.write_text(CATALOG_SOURCE, encoding="utf-8")
        created.append(str(catalog_path))

    registry_path = mordor_dir / REGISTRY_FILE
    if not registry_path.exists():
        _write_json(registry_path, _default_registry())
        created.append(str(registry_path))
    else:
        try:
            registry = _read_json(registry_path)
            changed = False
            if registry.get("version") is None:
                registry["version"] = 1
                changed = True
            if registry.get("helper_package") is None:
                registry["helper_package"] = HELPER_PACKAGE
                changed = True
            if _merge_default_helper(registry):
                changed = True
            if changed:
                _write_json(registry_path, registry)
                updated.append(str(registry_path))
        except Exception as exc:
            errors.append(f"{registry_path}: {exc}")

    if update_root_gitignore:
        try:
            if _append_root_gitignore(root):
                updated.append(str(root / ".gitignore"))
        except Exception as exc:
            errors.append(f"{root / '.gitignore'}: {exc}")

    status = helper_workspace_status(root)
    return {
        "ok": not errors,
        "created": created,
        "updated": updated,
        "errors": errors,
        **status,
    }
