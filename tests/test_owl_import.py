from pathlib import Path

from typer.testing import CliRunner

from leankg.cli import app
from leankg.domain.owl_import import import_ontology
from leankg.domain.pack import Ontology

FIXTURE = Path(__file__).parent / "fixtures" / "tiny_maintenance.ttl"


def test_import_keeps_ja_labels_and_structure() -> None:
    onto, rows = import_ontology(FIXTURE, "tiny")
    ents = onto["entities"]
    assert ents["Pump"]["labels"] == {"en": "Pump", "ja": "ポンプ"}
    assert ents["Pump"]["parent"] == "MaintainableItem"
    assert ents["FailureMode"]["description"] == "How an item fails."
    rel = onto["relations"]["HAS_FAILURE_MODE"]
    assert (rel["from"], rel["to"]) == (["MaintainableItem"], ["FailureMode"])
    assert rel["labels"]["ja"] == "故障モードを持つ"
    assert onto["relations"]["RELATED_TO"]["from"] == ["*"]
    Ontology.model_validate(onto)  # valid pack ontology
    by_lang = {r["lang"]: r for r in rows}
    assert by_lang["ja"]["term"] == "漏れ"
    assert by_lang["ja"]["synonyms"] == "リーク"
    assert by_lang["en"]["id"] == "tiny:Leak"


def test_cli_import_owl(tmp_path: Path) -> None:
    out, dic = tmp_path / "ontology.yaml", tmp_path / "terms.csv"
    result = CliRunner().invoke(
        app, ["import-owl", str(FIXTURE), "--out", str(out), "--dictionary", str(dic)]
    )
    assert result.exit_code == 0, result.output
    assert "Japanese labels" in result.output
    assert "ポンプ" in out.read_text(encoding="utf-8")
    assert "漏れ" in dic.read_text(encoding="utf-8")
