from mordornotebook.cli import build_parser


def test_cli_parses_doctor():
    args = build_parser().parse_args(["doctor", "--json"])
    assert args.command == "doctor"


def test_cli_parses_cell_insert():
    args = build_parser().parse_args(["cell", "insert", "--type", "markdown", "--text", "## Test"])
    assert args.cell_command == "insert"
    assert args.type == "markdown"


def test_cli_parses_jupyter_enable():
    args = build_parser().parse_args(["jupyter", "enable", "--sys-prefix"])
    assert args.jupyter_command == "enable"
    assert args.sys_prefix is True


def test_cli_parses_agent_cursor_backend():
    args = build_parser().parse_args(
        [
            "agent",
            "send",
            "--backend",
            "cursor",
            "--cursor-command",
            "cursor-agent",
            "--cursor-model",
            "sonnet-4",
            "--cursor-sandbox",
            "disabled",
            "--cursor-force",
            "--text",
            "hello",
        ]
    )
    assert args.agent_command == "send"
    assert args.backend == "cursor"
    assert args.cursor_command == "cursor-agent"
    assert args.cursor_model == "sonnet-4"
    assert args.cursor_sandbox == "disabled"
    assert args.cursor_force is True


def test_cli_parses_helpers_commands():
    ensure_args = build_parser().parse_args(["helpers", "ensure", "--repo", "/tmp/repo", "--json"])
    assert ensure_args.command == "helpers"
    assert ensure_args.helpers_command == "ensure"
    assert ensure_args.repo == "/tmp/repo"
    assert ensure_args.json is True

    list_args = build_parser().parse_args(["helpers", "list", "--repo", "/tmp/repo"])
    assert list_args.command == "helpers"
    assert list_args.helpers_command == "list"
    assert list_args.repo == "/tmp/repo"


def test_cli_cursor_force_defaults_to_config():
    args = build_parser().parse_args(["agent", "send", "--backend", "cursor", "--text", "hello"])

    assert args.backend == "cursor"
    assert args.cursor_force is None


def test_cli_parses_agent_stop():
    args = build_parser().parse_args(["agent", "stop", "--backend", "cursor", "--session", "mordor-test"])
    assert args.agent_command == "stop"
    assert args.backend == "cursor"
    assert args.session == "mordor-test"
