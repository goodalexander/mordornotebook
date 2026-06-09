import importlib
import sys

from mordornotebook.helpers import ensure_helper_workspace, helper_workspace_status


def test_ensure_helper_workspace_creates_trackable_helper_scaffold(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    result = ensure_helper_workspace(repo)

    assert result["ok"] is True
    assert (repo / "mordor" / "helpers.json").exists()
    assert (repo / "mordor" / "HELPERS.md").exists()
    assert (repo / "mordor" / ".gitignore").exists()
    assert (repo / "mordorhelper" / "__init__.py").exists()
    assert (repo / "mordorhelper" / "catalog.py").exists()

    root_gitignore = (repo / ".gitignore").read_text(encoding="utf-8")
    root_gitignore_lines = set(root_gitignore.splitlines())
    assert "/mordor/cache/" in root_gitignore_lines
    assert "/mordor/tmp/" in root_gitignore_lines
    assert "/mordor/" not in root_gitignore_lines
    assert "/mordorhelper/" not in root_gitignore_lines

    status = helper_workspace_status(repo)
    assert status["available"] is True
    assert status["helper_count"] == 1
    helper = status["registry"]["helpers"][0]
    assert helper["id"] == "helper_catalog"
    assert helper["import_path"] == "mordorhelper.catalog.HelperCatalog"
    assert "plain-English" not in helper["description"]
    assert "Reads the repo-local Mordor helper manifest" in helper["description"]


def test_repo_local_mordorhelper_catalog_is_importable(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    elsewhere = tmp_path / "elsewhere"
    repo.mkdir()
    elsewhere.mkdir()
    ensure_helper_workspace(repo)
    monkeypatch.chdir(elsewhere)
    monkeypatch.syspath_prepend(str(repo))
    sys.modules.pop("mordorhelper", None)
    sys.modules.pop("mordorhelper.catalog", None)

    module = importlib.import_module("mordorhelper.catalog")
    helpers = module.HelperCatalog().list()

    assert helpers[0]["id"] == "helper_catalog"
