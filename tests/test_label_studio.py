import json
import xml.etree.ElementTree as ET
from pathlib import Path

from typer.testing import CliRunner

from leankg.cli import app
from leankg.domain.loader import load_pack
from leankg.eval.gold import load_gold
from leankg.eval.label_studio import convert_export, labeling_config, make_tasks
from leankg.eval.preannotate import doc_to_example

from .helpers import run_stages

runner = CliRunner()


def test_config_is_valid_xml_with_all_types() -> None:
    pack = load_pack("manufacturing")
    root = ET.fromstring(labeling_config(pack, "ja"))
    labels = {e.get("value") for e in root.iter("Label")}
    rels = {e.get("value") for e in root.iter("Relation")}
    assert labels == set(pack.entity_types)
    assert rels == {*pack.relation_types, "negated"}
    text = next(root.iter("Text"))
    assert text.get("granularity") == "symbol"  # character spans for Japanese
    assert any(e.get("hint") == "故障モード" for e in root.iter("Label"))


def _export() -> list[dict[str, object]]:
    return [
        {
            "id": 1,
            "data": {"id": "mf-ja-001", "lang": "ja", "text": "摩耗は漏れの原因ではなかった。"},
            "annotations": [
                {"was_cancelled": True, "result": []},
                {
                    "updated_at": "2026-11-21T10:00:00",
                    "result": [
                        {"id": "a", "type": "labels", "from_name": "label", "to_name": "text",
                         "value": {"start": 0, "end": 2, "text": "摩耗", "labels": ["Cause"]}},
                        {"id": "b", "type": "labels", "from_name": "label", "to_name": "text",
                         "value": {"start": 3, "end": 5, "text": "漏れ", "labels": ["FailureMode"]}},
                        {"type": "relation", "from_id": "b", "to_id": "a", "direction": "right",
                         "labels": ["CAUSED_BY", "negated"]},
                    ],
                },
            ],
        },
        {"id": 2, "data": {"text": "未ラベル"}, "annotations": []},
    ]  # fmt: skip


def test_convert_export() -> None:
    examples, warnings = convert_export(_export())  # type: ignore[arg-type]
    assert len(examples) == 1
    assert any("no (non-cancelled) annotation" in w for w in warnings)
    ex = examples[0]
    assert ex.id == "mf-ja-001"
    assert ex.lang == "ja"
    assert [(e.text, e.type) for e in ex.entities] == [("摩耗", "Cause"), ("漏れ", "FailureMode")]
    rel = ex.relations[0]
    assert (rel.head, rel.tail, rel.type, rel.negated) == (1, 0, "CAUSED_BY", True)


def test_tasks_with_preannotations_roundtrip() -> None:
    text = "潤滑不足によりベアリングの焼き付きが発生した。"
    doc = run_stages(
        text,
        ("ingest", "preprocess", "dictionary", "regex", "linking", "dependency", "trigger",
         "cooc", "negation", "validate"),
        "manufacturing",
    )  # fmt: skip
    pred = doc_to_example(doc, "ja", "x")
    tasks = make_tasks([text], "ja", "mf", [pred])
    assert tasks[0]["predictions"][0]["result"]
    # pretend the annotator accepted the predictions as-is
    tasks[0]["annotations"] = [{"result": tasks[0]["predictions"][0]["result"]}]
    back, _ = convert_export(tasks)
    assert [e.text for e in back[0].entities] == [e.text for e in pred.entities]
    assert len(back[0].relations) == len(pred.relations)


def test_cli_labelstudio_convert(tmp_path: Path) -> None:
    src = tmp_path / "export.json"
    src.write_text(json.dumps(_export(), ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "gold.ja.jsonl"
    result = runner.invoke(
        app, ["labelstudio", "convert", str(src), "--out", str(out), "--domain", "manufacturing"]
    )
    assert result.exit_code == 0, result.output
    assert load_gold(out)[0].relations[0].negated is True


def test_cli_labelstudio_config() -> None:
    result = runner.invoke(app, ["labelstudio", "config", "--domain", "health_stress"])
    assert result.exit_code == 0
    assert "<View>" in result.output
