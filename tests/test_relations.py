"""Rule-only relation extraction tests (dependency patterns, triggers, negation, validation)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from leankg.models import Document

from .conftest import requires_en_model, requires_ginza
from .helpers import run_stages

FIXTURES = Path(__file__).parent / "fixtures"
RULE_STAGES = (
    "ingest", "preprocess", "dictionary", "regex", "linking",
    "dependency", "trigger", "cooc", "negation", "validate",
)  # fmt: skip


def _cases(pack: str, lang: str) -> list[dict[str, Any]]:
    data = yaml.safe_load((FIXTURES / f"relations_{pack}.yaml").read_text(encoding="utf-8"))
    return list(data[lang])


def _parse(expect: str) -> tuple[str, str, str, set[str]]:
    triple, _, flags = expect.partition("|")
    head, rel, tail = (p.strip() for p in triple.split(">"))
    return head, rel, tail, set(flags.split())


def _found(doc: Document) -> dict[tuple[str, str, str], Any]:
    ms = doc.mention_index()
    return {(ms[t.head_mention].text, t.type, ms[t.tail_mention].text): t for t in doc.triples}


def _check(pack: str, case: dict[str, Any]) -> None:
    doc = run_stages(case["text"], RULE_STAGES, pack)
    found = _found(doc)
    for expect in case["expect"]:
        head, rel, tail, flags = _parse(expect)
        t = found.get((head, rel, tail))
        assert t is not None, f"{case['text']}: missing {expect}; found {sorted(found)}"
        assert t.negated == ("neg" in flags), f"{expect}: negated={t.negated}"
        assert t.hedged == ("hedge" in flags), f"{expect}: hedged={t.hedged}"
        assert t.complex == ("complex" in flags), f"{expect}: complex={t.complex}"
        if "complex" in flags or "candidate" in flags:
            assert t.status == "candidate"
        else:
            assert t.status == ("negative" if "neg" in flags else "accepted"), t.status
        # provenance on every edge
        assert t.provenance
        p = t.provenance[0]
        assert (p.doc_id, p.lang, p.method) == ("t", doc.lang, t.method)
        assert t.head
        assert t.tail


@requires_en_model
@pytest.mark.parametrize("case", _cases("health_stress", "en"), ids=lambda c: c["text"][:40])
def test_health_en(case: dict[str, Any]) -> None:
    _check("health_stress", case)


@requires_ginza
@pytest.mark.parametrize("case", _cases("health_stress", "ja"), ids=lambda c: c["text"][:20])
def test_health_ja(case: dict[str, Any]) -> None:
    _check("health_stress", case)


@requires_en_model
@pytest.mark.parametrize("case", _cases("manufacturing", "en"), ids=lambda c: c["text"][:40])
def test_manufacturing_en(case: dict[str, Any]) -> None:
    _check("manufacturing", case)


@requires_ginza
@pytest.mark.parametrize("case", _cases("manufacturing", "ja"), ids=lambda c: c["text"][:20])
def test_manufacturing_ja(case: dict[str, Any]) -> None:
    _check("manufacturing", case)


def test_fixture_counts_meet_the_spec() -> None:
    for pack in ("health_stress", "manufacturing"):
        for lang in ("en", "ja"):
            assert len(_cases(pack, lang)) >= 15, (pack, lang)


# ------------------------------------------------- behaviour without a parser
def test_ja_triggers_work_without_ginza() -> None:
    """Script-run tokenizer has no parse: triggers still find the relation."""
    from leankg.lang.ja import JapaneseProfile, ScriptRunTokenizer

    from .helpers import make_ctx

    ctx = make_ctx("health_stress")
    import spacy

    nlp = spacy.blank("xx")
    nlp.tokenizer = ScriptRunTokenizer(nlp.vocab)
    profile = JapaneseProfile()
    profile._nlp_cache = {"ja_ginza": nlp}  # instance-level override
    ctx.profiles = type(ctx.get_profiles())()
    ctx.profiles.register(profile)
    from leankg.pipeline import Pipeline

    doc = Pipeline(ctx=ctx, stage_names=list(RULE_STAGES)).run(
        [Document(id="t", text="運動は不安を軽減する。")]
    )[0]
    found = _found(doc)
    t = found[("運動", "REDUCES", "不安")]
    assert t.method == "trigger"
    assert t.status == "accepted"


def test_schema_violations_are_dropped() -> None:
    # Biomarker cannot REDUCE anything: the trigger fires but validation drops it.
    doc = run_stages("Cortisol reduces exercise.", RULE_STAGES)
    assert not [t for t in doc.triples if t.type == "REDUCES"]


def test_cooc_candidates_need_an_allowed_type_pair() -> None:
    doc = run_stages("Yoga and cortisol were both mentioned.", RULE_STAGES)
    cands = [t for t in doc.triples if t.method == "cooc"]
    assert cands
    assert all(t.status == "candidate" for t in cands)
    assert cands[0].type == "REDUCES"  # specific relation preferred over ASSOCIATED_WITH


def test_duplicate_evidence_is_merged_in_graph() -> None:
    from leankg.graph import KnowledgeGraph

    g = KnowledgeGraph()
    for i, text in enumerate(
        ["Work stress causes burnout.", "職場ストレスは燃え尽き症候群を引き起こす。"]
    ):
        g.add_document(run_stages(text, RULE_STAGES, doc_id=f"d{i}"))
    t = g.triples[("HS:work_stress", "HS:burnout", "INCREASES_RISK_OF", False)]
    assert t.evidence_count == 2
    assert t.langs == ["en", "ja"]
    assert t.doc_ids == ["d0", "d1"]
