import pytest

from .conftest import requires_ginza
from .helpers import ENTITY_STAGES, mentions, run_stages


# ----------------------------------------------------------------- English
def test_en_dictionary_longest_match_and_plural() -> None:
    found = mentions("Chronic stress causes headaches and major depressive disorder.")
    assert ("Chronic stress", "Stressor", "dict") in found
    assert ("headaches", "Symptom", "dict") in found
    assert ("major depressive disorder", "Condition", "dict") in found
    assert not any(t == "stress" for t, _, _ in found)  # inside the longer match


def test_en_dictionary_is_case_insensitive() -> None:
    found = mentions("COGNITIVE BEHAVIORAL THERAPY and Yoga.")
    assert ("COGNITIVE BEHAVIORAL THERAPY", "Intervention", "dict") in found
    assert ("Yoga", "Intervention", "dict") in found


def test_en_regex_entities() -> None:
    found = mentions("Scores on the K-10 and IL-6 were recorded.")
    assert ("K-10", "Instrument", "regex") in found
    assert ("IL-6", "Biomarker", "dict") in found  # dictionary wins over regex


# ---------------------------------------------------------------- Japanese
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("油圧ポンプが故障した。", ("油圧ポンプ", "Component")),
        ("ベアリングの摩耗を確認。", ("摩耗", "Cause")),
        ("ﾍﾞｱﾘﾝｸﾞを交換した。", ("ﾍﾞｱﾘﾝｸﾞ", "Component")),  # half-width kana
        ("ポカよけを導入した。", ("ポカよけ", "TPSConcept")),
        ("ぽかよけを導入した。", ("ぽかよけ", "TPSConcept")),  # hiragana vs katakana
        ("モータの過熱", ("モータ", "Component")),  # long-vowel variant
        ("ジャストインタイム生産", ("ジャストインタイム", "TPSConcept")),
    ],
)
def test_ja_dictionary_char_matching(text: str, expected: tuple[str, str]) -> None:
    found = [(t, ty) for t, ty, _ in mentions(text, "manufacturing")]
    assert expected in found


def test_ja_longest_match_wins() -> None:
    found = [(t, ty) for t, ty, _ in mentions("職場ストレスと不安障害。")]
    assert ("職場ストレス", "Stressor") in found
    assert ("不安障害", "Condition") in found
    assert ("ストレス", "Stressor") not in found
    assert ("不安", "Symptom") not in found


def test_ja_offsets_point_at_original_text() -> None:
    doc = run_stages("本日、ｵｲﾙｼｰﾙからｵｲﾙ漏れ。", ENTITY_STAGES, "manufacturing")
    sent = next(doc.sentences())
    for m in doc.mentions:
        assert sent.text[m.start : m.end] == m.text
    assert {m.text for m in doc.mentions} >= {"ｵｲﾙｼｰﾙ", "ｵｲﾙ漏れ"}


def test_ja_regex_full_width_digits() -> None:
    found = mentions("マシニングセンタにエラーコードＥ－１２３４が表示された。", "manufacturing")
    assert any(ty == "Observation" and "１２３４" in t for t, ty, m in found if m == "regex")


def test_ja_regex_scale_code_full_width() -> None:
    found = mentions("うつ病はＰＨＱ－９で評価した。")
    assert ("ＰＨＱ－９", "Instrument", "dict") in found or (
        "ＰＨＱ－９",
        "Instrument",
        "regex",
    ) in found


@requires_ginza
def test_ja_terms_that_sudachi_splits_still_match() -> None:
    """Sudachi may tokenize compounds differently; char matching must not care."""
    doc = run_stages("油圧ポンプと産業用ロボットと燃え尽き症候群", ENTITY_STAGES, "manufacturing")
    sdoc = next(doc.sentences()).spacy_doc
    tokens = [t.text for t in sdoc]
    assert "油圧ポンプ" not in tokens or "産業用ロボット" not in tokens  # at least one is split
    texts = {m.text for m in doc.mentions}
    assert {"油圧ポンプ", "産業用ロボット"} <= texts


# ------------------------------------------------------------------ linking
def test_cross_language_linking_to_same_entity() -> None:
    doc = run_stages("Stress causes insomnia.\n\nストレスは不眠を引き起こす。", ENTITY_STAGES)
    by_id = {e.id: e for e in doc.entities}
    assert "HS:stress" in by_id
    stress = by_id["HS:stress"]
    assert stress.lang_seen == ["en", "ja"]
    assert stress.name == "stress"
    assert stress.name_ja == "ストレス"
    assert "ストレス" in stress.aliases_for("ja")
    assert by_id["HS:insomnia"].mention_count == 2


def test_unlinked_regex_mention_gets_typed_entity_id() -> None:
    doc = run_stages("Alarm code 4521 on line 3.", ENTITY_STAGES, "manufacturing")
    m = next(m for m in doc.mentions if m.method == "regex")
    assert m.entity_id == "manufacturing:Observation:alarm code 4521"


def test_provenance_on_entities() -> None:
    doc = run_stages("Yoga helps.", ENTITY_STAGES)
    ent = next(e for e in doc.entities if e.id == "HS:yoga")
    p = ent.provenance[0]
    assert (p.doc_id, p.method, p.lang) == ("t", "dict", "en")
    chunk = doc.chunks[0]
    assert chunk.text[p.start : p.end] == "Yoga"
