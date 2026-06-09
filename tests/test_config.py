from mordornotebook.config import MordorConfig, load_config, save_config, secrets_permissions_status


def test_config_roundtrip(tmp_path):
    path = tmp_path / "config.toml"
    save_config(
        MordorConfig(
            default_repo="/tmp/repo",
            agent_backend="cursor",
            cursor_command="cursor-agent",
            cursor_model="sonnet-4",
            cursor_sandbox="disabled",
            cursor_force=True,
            context_max_chars=123,
        ),
        path=path,
    )
    loaded = load_config(path)
    assert loaded.default_repo == "/tmp/repo"
    assert loaded.agent_backend == "cursor"
    assert loaded.cursor_model == "sonnet-4"
    assert loaded.cursor_sandbox == "disabled"
    assert loaded.cursor_force is True
    assert loaded.context_max_chars == 123


def test_env_default_repo_fills_missing_config(monkeypatch, tmp_path):
    monkeypatch.setenv("MORDOR_REPO", "/tmp/env-repo")

    loaded = load_config(tmp_path / "missing.toml")

    assert loaded.default_repo == "/tmp/env-repo"


def test_config_default_repo_wins_over_env(monkeypatch, tmp_path):
    monkeypatch.setenv("MORDOR_REPO", "/tmp/env-repo")
    path = tmp_path / "config.toml"
    save_config(MordorConfig(default_repo="/tmp/config-repo"), path=path)

    loaded = load_config(path)

    assert loaded.default_repo == "/tmp/config-repo"


def test_missing_secrets_file_is_secure(tmp_path):
    status = secrets_permissions_status(tmp_path / "missing.toml")
    assert status["exists"] is False
    assert status["secure"] is True
