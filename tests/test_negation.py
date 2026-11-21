import pytest

from leankg.lang import en_rules, ja_rules


def _en(text: str, a: str, b: str) -> tuple[bool, bool, bool]:
    ha, hb = text.index(a), text.index(b)
    return en_rules.negation_hedge(text, (ha, ha + len(a)), (hb, hb + len(b)))


def _ja(text: str, a: str, b: str) -> tuple[bool, bool, bool]:
    ha, hb = text.index(a), text.index(b)
    return ja_rules.negation_hedge(text, (ha, ha + len(a)), (hb, hb + len(b)))


@pytest.mark.parametrize(
    ("text", "a", "b", "expected"),
    [
        ("Yoga did not reduce blood pressure.", "Yoga", "blood pressure", (True, False, False)),
        ("Yoga didn't reduce blood pressure.", "Yoga", "blood pressure", (True, False, False)),
        ("Stress may cause insomnia.", "Stress", "insomnia", (False, True, False)),
        ("Stress appears to cause insomnia.", "Stress", "insomnia", (False, True, False)),
        ("Stress causes insomnia.", "Stress", "insomnia", (False, False, False)),
        ("Exercise was not associated with anxiety.", "Exercise", "anxiety", (True, False, False)),
        ("It cannot be ruled out that stress causes insomnia.", "stress", "insomnia",
         (False, False, True)),
        ("Stress did not fail to cause insomnia.", "Stress", "insomnia", (False, False, True)),
        # negation in another clause does not leak in
        ("Stress causes insomnia; exercise did not help.", "Stress", "insomnia",
         (False, False, False)),
        ("The error appeared on the CNC machine.", "error", "CNC machine", (False, False, False)),
    ],
)  # fmt: skip
def test_en_negation_hedge(text: str, a: str, b: str, expected: tuple[bool, bool, bool]) -> None:
    assert _en(text, a, b) == expected


@pytest.mark.parametrize(
    ("text", "a", "b", "expected"),
    [
        ("運動はストレスを軽減しなかった。", "運動", "ストレス", (True, False, False)),
        ("運動はストレスを軽減しない。", "運動", "ストレス", (True, False, False)),
        ("運動はストレスを軽減しません。", "運動", "ストレス", (True, False, False)),
        ("摩耗が漏れの原因である可能性がある。", "摩耗", "漏れ", (False, True, False)),
        ("摩耗が漏れの原因かもしれない。", "摩耗", "漏れ", (False, True, False)),  # ない inside hedge
        ("ストレスが不眠の原因でないとは言えない。", "ストレス", "不眠", (False, False, True)),
        ("ストレスが不眠の原因でないわけではない。", "ストレス", "不眠", (False, False, True)),
        ("摩耗は漏れを少なくする。", "摩耗", "漏れ", (False, False, False)),  # 少なく
        ("運動はストレスを軽減する。", "運動", "ストレス", (False, False, False)),
        # negation after the clause boundary is out of scope
        ("運動はストレスを軽減するが、瞑想は効果がなかった。", "運動", "ストレス",
         (False, False, False)),
    ],
)  # fmt: skip
def test_ja_negation_hedge(text: str, a: str, b: str, expected: tuple[bool, bool, bool]) -> None:
    assert _ja(text, a, b) == expected


def test_extra_cues_from_pack() -> None:
    text = "Stress is unrelated with insomnia."
    a, b = text.index("Stress"), text.index("insomnia")
    assert en_rules.negation_hedge(text, (a, a + 6), (b, b + 8), extra_neg=["unrelated"])[0]


def test_negspacy_cues_used_when_installed() -> None:
    pytest.importorskip("negspacy")
    assert "free of" in en_rules.negspacy_cues() or len(en_rules.negspacy_cues()) > 10
