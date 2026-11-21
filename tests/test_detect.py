import pytest

from leankg.lang.detect import cjk_ratio, detect_language


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Chronic stress increases the risk of insomnia.", "en"),
        ("慢性的なストレスは不眠のリスクを高める。", "ja"),
        ("油圧ポンプのベアリングが摩耗した。", "ja"),
        ("ｽﾄﾚｽは睡眠障害を引き起こす。", "ja"),  # half-width katakana
        # mixed: Japanese manual sentence with English part names stays Japanese
        ("Replace the hydraulic pump (P/N 12-345) if 油圧 is low.", "en"),
        ("ポンプ P/N 12-345 の Bearing を交換すること。", "ja"),
        ("", "en"),
        ("   ", "en"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


def test_default_for_empty_text() -> None:
    assert detect_language("", default="ja") == "ja"


def test_ratio_bounds() -> None:
    assert cjk_ratio("abc") == 0.0
    assert cjk_ratio("ストレス") == 1.0
    assert 0.0 < cjk_ratio("stress ストレス") < 1.0


def test_threshold_is_configurable() -> None:
    text = "pump ポンプ bearing"  # 3 of 14 counted chars are kana
    assert detect_language(text, threshold=0.1) == "ja"
    assert detect_language(text, threshold=0.5) == "en"
