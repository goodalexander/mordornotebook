import pytest


@pytest.fixture(autouse=True)
def isolated_mordor_dirs(monkeypatch, tmp_path):
    monkeypatch.setenv("MORDOR_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("MORDOR_STATE_DIR", str(tmp_path / "state"))
