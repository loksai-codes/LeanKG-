from typer.testing import CliRunner

from leankg.cli import app

runner = CliRunner()


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ("build", "eval", "review-llm", "llm-models", "import-owl"):
        assert cmd in result.output


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "leankg" in result.output
