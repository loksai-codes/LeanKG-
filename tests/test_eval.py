import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from leankg.cli import app
from leankg.eval.converters import NCBI_TYPE_MAP, pubtator_to_gold, read_pubtator
from leankg.eval.gold import GoldExample, dump_gold, load_gold
from leankg.eval.harness import (
    check_baseline,
    gold_path,
    run_eval,
    update_baseline,
)
from leankg.eval.metrics import (
    Prediction,
    PredMention,
    PredRelation,
    entity_scores,
    linking_counts,
    relation_scores,
)

from .conftest import DOMAINS

runner = CliRunner()


def _ex() -> GoldExample:
    return GoldExample.model_validate(
        {
            "id": "x",
            "lang": "en",
            "text": "Stress causes insomnia and stress.",
            "entities": [
                {"text": "Stress", "type": "Stressor", "id": "HS:stress"},
                {"text": "insomnia", "type": "Condition", "id": "HS:insomnia"},
                {"text": "stress", "type": "Stressor", "occurrence": 1},
            ],
            "relations": [{"head": 0, "tail": 1, "type": "INCREASES_RISK_OF"}],
        }
    )


def test_gold_offsets_resolved_from_text() -> None:
    ex = _ex()
    assert [(e.start, e.end) for e in ex.entities] == [(0, 6), (14, 22), (27, 33)]


def test_gold_validation_errors(tmp_path: Path) -> None:
    p = tmp_path / "g.jsonl"
    p.write_text(
        '{"id": "a", "lang": "en", "text": "x", "entities": [{"text": "y", "type": "T"}]}\n'
    )
    with pytest.raises(ValueError, match=r"(?s)g.jsonl:1: .*not found"):
        load_gold(p)


def test_gold_roundtrip(tmp_path: Path) -> None:
    path = dump_gold([_ex()], tmp_path / "g.jsonl")
    again = load_gold(path)
    assert again[0].entities[1].start == 14


def test_entity_scores_exact_and_partial() -> None:
    ex = _ex()
    pred = Prediction(
        mentions=[
            PredMention(0, 6, "Stressor", "HS:stress"),  # exact
            PredMention(14, 20, "Condition", None),  # partial only
            PredMention(27, 33, "Symptom", None),  # wrong type
        ]
    )
    exact, partial = entity_scores(ex, pred)
    assert (exact.tp, exact.fp, exact.fn) == (1, 2, 2)
    assert (partial.tp, partial.fp, partial.fn) == (2, 1, 1)
    assert linking_counts(ex, pred) == (1, 1)


def test_relation_scores_direction_and_negation() -> None:
    ex = _ex()
    good = PredRelation((0, 6), (14, 22), "INCREASES_RISK_OF", False)
    reversed_ = PredRelation((14, 22), (0, 6), "INCREASES_RISK_OF", False)
    negated = PredRelation((0, 6), (14, 22), "INCREASES_RISK_OF", True)
    assert relation_scores(ex, Prediction(relations=[good])).f1 == 1.0
    assert relation_scores(ex, Prediction(relations=[reversed_])).tp == 0
    assert relation_scores(ex, Prediction(relations=[negated])).tp == 0


def test_symmetric_relations_match_either_way() -> None:
    ex = GoldExample.model_validate(
        {"id": "s", "lang": "en", "text": "A and B",
         "entities": [{"text": "A", "type": "T"}, {"text": "B", "type": "T"}],
         "relations": [{"head": 0, "tail": 1, "type": "ASSOCIATED_WITH"}]}
    )  # fmt: skip
    pred = Prediction(relations=[PredRelation((6, 7), (0, 1), "ASSOCIATED_WITH", False)])
    assert relation_scores(ex, pred).tp == 1


@pytest.mark.parametrize("pack", ["health_stress", "manufacturing"])
@pytest.mark.parametrize("lang", ["en", "ja"])
def test_fixtures_exist_and_are_valid(pack: str, lang: str) -> None:
    path = gold_path(pack, lang, fixtures=True)
    assert path is not None
    examples = load_gold(path)
    assert 15 <= len(examples) <= 20
    assert all(ex.lang == lang and ex.source == "seed" for ex in examples)


def test_run_eval_setup_a_and_baseline(tmp_path: Path) -> None:
    report = run_eval("health_stress", "A", ["en"], fixtures=True)
    r = report.results[0]
    assert r.n_examples >= 15
    assert r.llm_call_rate == 0.0
    assert "ner" in r.skipped_stages
    assert "| health_stress | en | A |" in report.to_markdown()
    base = update_baseline(report, tmp_path / "baseline.json")
    assert check_baseline(report, base) == []
    data = json.loads(base.read_text())
    data["health_stress/en/A"]["entity_f1"] = 1.5  # impossible -> regression
    base.write_text(json.dumps(data))
    assert check_baseline(report, base)


def test_type_filter_skips_relations(tmp_path: Path) -> None:
    report = run_eval("health_stress", "A", ["en"], fixtures=True, types=["Condition"])
    r = report.results[0]
    assert r.relation == {}
    assert "| – | – | – |" in report.to_markdown()


def test_committed_baseline_covers_ci_runs() -> None:
    path = DOMAINS.parent / "tests" / "fixtures" / "eval_baseline.json"
    base = json.loads(path.read_text(encoding="utf-8"))
    for pack in ("health_stress", "manufacturing"):
        for lang in ("en", "ja"):
            assert f"{pack}/{lang}/B" in base


def test_cli_eval(tmp_path: Path) -> None:
    result = runner.invoke(
        app,
        ["eval", "--domain", "manufacturing", "--setup", "A", "--fixtures", "--lang", "en",
         "--reports", str(tmp_path)],
    )  # fmt: skip
    assert result.exit_code == 0, result.output
    assert "| manufacturing | en | A |" in result.output
    assert list(tmp_path.glob("*_manufacturing_A.json"))


PUBTATOR = """\
1|t|Chronic insomnia and depression.
1|a|Patients with major depression often report insomnia. Nothing else here.
1\t8\t16\tinsomnia\tSpecificDisease\tD007319
1\t21\t31\tdepression\tSpecificDisease\tD003866
1\t47\t63\tmajor depression\tSpecificDisease\tD003865
1\t77\t85\tinsomnia\tSpecificDisease\tD007319

"""


def test_pubtator_converter(tmp_path: Path) -> None:
    p = tmp_path / "corpus.txt"
    p.write_text(PUBTATOR, encoding="utf-8")
    docs = list(read_pubtator(p))
    assert len(docs) == 1
    assert len(docs[0].annotations) == 4
    gold = pubtator_to_gold(p, NCBI_TYPE_MAP, "ncbi")
    assert [g.text for g in gold][:2] == [
        "Chronic insomnia and depression.",
        "Patients with major depression often report insomnia.",
    ]
    assert [e.text for e in gold[1].entities] == ["major depression", "insomnia"]
    assert all(e.type == "Condition" for g in gold for e in g.entities)
    assert gold[2].entities == []
    assert len(pubtator_to_gold(p, NCBI_TYPE_MAP, "ncbi", keep_empty=False)) == 2


def test_gold_offsets_realigned_after_cleaning() -> None:
    from leankg.eval.harness import _align_to_clean

    ex = GoldExample.model_validate(
        {"id": "a", "lang": "en", "text": "Stress  causes   insomnia.",
         "entities": [{"text": "insomnia", "type": "Condition"}]}
    )  # fmt: skip
    out = _align_to_clean(ex)
    assert out.text == "Stress causes insomnia."
    assert out.entities[0].text == "insomnia"
