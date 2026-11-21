import pytest
from pydantic import ValidationError

from leankg.models import (
    Chunk,
    Document,
    LangStats,
    LLMVerdict,
    Mention,
    RunReport,
    Sentence,
)


def _doc() -> Document:
    sent = Sentence(
        id="d:c0:s0", doc_id="d", chunk_id="d:c0", index=0, start=0, end=5, text="Hello", lang="en"
    )
    chunk = Chunk(
        id="d:c0", doc_id="d", index=0, start=0, end=5, text="Hello", lang="en", sentences=[sent]
    )
    return Document(id="d", text="Hello", chunks=[chunk])


def _mention(mid: str, start: int, end: int) -> Mention:
    return Mention(
        id=mid,
        doc_id="d",
        chunk_id="c",
        sent_id="s",
        start=start,
        end=end,
        text="x" * (end - start),
        type="T",
        method="dict",
        lang="en",
        confidence=1.0,
    )


def test_document_sentence_iteration() -> None:
    doc = _doc()
    assert [s.id for s in doc.sentences()] == ["d:c0:s0"]
    assert "d:c0:s0" in doc.sentence_index()


def test_sentence_spacy_doc_is_private_and_not_serialized() -> None:
    doc = _doc()
    sent = next(doc.sentences())
    sent.set_spacy_doc(object())
    assert sent.spacy_doc is not None
    assert "_spacy" not in doc.model_dump_json()


def test_mention_overlap() -> None:
    a, b, c = _mention("a", 0, 5), _mention("b", 4, 8), _mention("c", 5, 8)
    assert a.overlaps(b)
    assert not a.overlaps(c)


def test_rates_are_zero_safe() -> None:
    s = LangStats()
    assert s.llm_call_rate == 0.0
    assert s.cache_hit_rate == 0.0
    s = LangStats(
        sentences=100, llm_sentences=8, cache_hits=6, dedupe_hits=2, hard_case_sentences=12
    )
    assert s.llm_call_rate == 0.08
    assert s.cache_hit_rate == 1.0
    assert s.hard_case_rate == 0.12


def test_run_report_has_required_fields() -> None:
    r = RunReport(docs=10, est_cost_usd=0.02, duration_s=30)
    dumped = r.model_dump()
    for key in ("llm_call_rate", "cache_hit_rate", "est_cost_usd", "by_lang"):
        assert key in dumped
    assert r.cost_per_1k_docs_usd == pytest.approx(2.0)
    assert r.docs_per_min == pytest.approx(20.0)
    r.lang("ja").sentences += 3
    assert r.by_lang["ja"].sentences == 3


def test_verdict_confidence_bounds() -> None:
    bad = {"case_id": "c", "relations": [{"head": 0, "tail": 1, "type": "X", "confidence": 1.5}]}
    with pytest.raises(ValidationError):
        LLMVerdict.model_validate(bad)
