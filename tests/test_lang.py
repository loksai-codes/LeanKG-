import pytest

from leankg.lang.base import ProfileRegistry, make_profile
from leankg.lang.en import EnglishProfile
from leankg.lang.ja import JapaneseProfile, ScriptRunTokenizer, hira2kata
from leankg.lang.text import nfkc_with_map

from .conftest import requires_ginza

JA = JapaneseProfile()
EN = EnglishProfile()


# ------------------------------------------------------------ normalization
@pytest.mark.parametrize(
    ("a", "b"),
    [
        ("ストレス", "すとれす"),  # katakana vs hiragana
        ("ひずみ", "ヒズミ"),
        ("ｽﾄﾚｽ", "ストレス"),  # half-width kana
        ("ﾓｰﾀｰ", "モーター"),  # half-width with long vowel
        ("モーター", "モータ"),  # long-vowel variants
        ("モ－タ－", "モーター"),  # full-width hyphen used as long vowel
        ("ＰＵＭＰ", "pump"),  # full-width Latin + case
        ("５ｍｇ", "5mg"),  # full-width digits/letters
        ("ガ", "ｶﾞ"),  # half-width voiced mark composes
    ],
)
def test_ja_normalize_equivalences(a: str, b: str) -> None:
    assert JA.normalize(a) == JA.normalize(b)


def test_ja_normalize_keeps_hyphen_in_codes() -> None:
    assert JA.normalize("Ｅ－１２３４") == "e-1234"


def test_ja_offset_map_round_trip() -> None:
    text = "本日ｶﾞｽの漏れ"  # half-width ｶﾞ is two chars that become one
    nt = JA.normalize_map(text)
    assert nt.text == "本日ガスノ漏レ"
    start = nt.text.index("ガス")
    assert nt.to_original(start, start + 2) == (2, 5)
    assert text[2:5] == "ｶﾞｽ"


def test_nfkc_map_handles_length_change() -> None:
    nt = nfkc_with_map("用量５㎎")
    assert nt.text == "用量5mg"
    assert nt.to_original(2, 5) == (2, 4)


def test_hira2kata() -> None:
    assert hira2kata("ぽかよけ") == "ポカヨケ"


def test_en_normalize() -> None:
    assert EN.normalize("  Chronic   STRESS ") == "chronic stress"
    assert EN.normalize("ＣＯＲＴＩＳＯＬ") == "cortisol"


@pytest.mark.parametrize(
    ("term", "variant"),
    [
        ("headache", "headaches"),
        ("anxiety disorder", "anxiety disorders"),
        ("therapy", "therapies"),
        ("bearing", "bearings"),
        ("brush", "brushes"),
    ],
)
def test_en_plural_variants(term: str, variant: str) -> None:
    assert variant in EN.term_variants(term)


def test_en_no_variant_for_codes() -> None:
    assert EN.term_variants("PHQ-9") == ["PHQ-9"]


# -------------------------------------------------------------- sentences
def _sents(profile: EnglishProfile | JapaneseProfile, text: str) -> list[str]:
    return [text[s:e] for s, e in profile.split_sentences(text)]


def test_en_sentence_split() -> None:
    text = "Stress causes insomnia. Dr. Smith agrees, e.g. in Fig. 2. Exercise helps!\n\nNext para"
    assert _sents(EN, text) == [
        "Stress causes insomnia.",
        "Dr. Smith agrees, e.g. in Fig. 2.",
        "Exercise helps!",
        "Next para",
    ]


def test_ja_sentence_split() -> None:
    text = "ストレスは不眠を引き起こす。運動は有効か？「瞑想が効く！」と彼は言った\n次の行"
    assert _sents(JA, text) == [
        "ストレスは不眠を引き起こす。",
        "運動は有効か？",
        "「瞑想が効く！」",
        "と彼は言った",
        "次の行",
    ]


def test_ja_split_offsets_are_exact() -> None:
    text = "  油圧ポンプが摩耗した。 漏れを検出した。"
    for s, e in JA.split_sentences(text):
        assert text[s:e].strip() == text[s:e]


# -------------------------------------------------------------- tokenizers
def test_script_run_tokenizer() -> None:
    import spacy

    nlp = spacy.blank("xx")
    nlp.tokenizer = ScriptRunTokenizer(nlp.vocab)
    doc = nlp("油圧ポンプのベアリングがE-1234で摩耗")
    assert [t.text for t in doc] == [
        "油圧", "ポンプ", "の", "ベアリング", "が", "E", "-", "1234", "で", "摩耗",
    ]  # fmt: skip
    assert doc.text == "油圧ポンプのベアリングがE-1234で摩耗"


def test_registry_caches_profiles() -> None:
    reg = ProfileRegistry()
    assert reg.get("ja") is reg.get("ja")
    assert reg.get("en").code == "en"
    with pytest.raises(KeyError):
        make_profile("fr")


@requires_ginza
def test_ginza_loads_and_bunsetsu_connect() -> None:
    nlp = JA.load_nlp()
    doc = nlp("ストレスが不眠を引き起こす。")
    assert doc.has_annotation("DEP")
    a = doc.char_span(0, 4, alignment_mode="expand")
    b = doc.char_span(5, 7, alignment_mode="expand")
    assert a is not None
    assert b is not None
    assert JA.connected(doc, a, b) is True
