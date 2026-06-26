from typer.testing import CliRunner
from cmpuse.cli import app


def test_cli_tools_lists_known_tools():
    r = CliRunner().invoke(app, ["tools"])
    assert r.exit_code == 0
    assert "json_ops" in r.stdout
    assert "fs_ops" in r.stdout

