from typer.testing import CliRunner

from incident_copilot import __version__
from incident_copilot.cli import app

runner = CliRunner()


def test_version_is_defined() -> None:
    assert __version__ == "0.1.0"


def test_cli_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "diagnose" in result.output
    assert "evals" in result.output


def test_diagnose_not_implemented_yet() -> None:
    result = runner.invoke(app, ["diagnose", "--scenario", "crashloop"])

    assert result.exit_code != 0
    assert isinstance(result.exception, NotImplementedError)
