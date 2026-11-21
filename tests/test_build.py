import json
from pathlib import Path

from typer.testing import CliRunner

from leankg.cli import app
from leankg.pipeline import Pipeline

from .conftest import ROOT

runner = CliRunner()


def test_pipeline_build_examples_json(tmp_path: Path) -> None:
    pipe = Pipeline.from_domain("health_stress", llm="none")
    report = pipe.build(ROOT / "examples" / "health_stress", out="json", out_path=tmp_path)
    assert report.docs == 3
    assert set(report.by_lang) == {"en", "ja"}
    assert report.by_lang["ja"].mentions > 0
    assert report.llm_call_rate == 0.0
    data = json.loads((tmp_path / "graph.json").read_text(encoding="utf-8"))
    assert any(e["id"] == "HS:stress" and e["lang_seen"] == ["en", "ja"] for e in data["entities"])


def test_cli_build_prints_report(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        [
            "build",
            str(ROOT / "examples" / "manufacturing"),
            "--domain",
            "manufacturing",
            "--llm",
            "none",
            "--out-path",
            str(tmp_path),
            "--csv-text-column",
            "summary",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "leankg run" in result.output
    assert "ja" in result.output
    assert (tmp_path / "graph.json").exists()
