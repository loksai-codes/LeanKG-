"""Japanese negation / hedging rules (docs/JAPANESE.md §7).

Japanese negation attaches to the predicate, which comes after the arguments, so the
scope is the text after the later mention up to the end of the clause. Hedge phrases are
removed before looking for negation because many contain ない (かもしれない).
"""

from __future__ import annotations

import re
from typing import Any

NEGATION_CUES: tuple[str, ...] = (
    "ませんでした", "なかった", "ません", "ない", "なく", "なし", "無し", "ず", "ぬ",
    "否定", "認められない", "見られない", "認めず",
)  # fmt: skip
HEDGE_CUES: tuple[str, ...] = (
    "かもしれない", "かもしれません", "可能性がある", "可能性があります", "可能性が高い",
    "可能性", "と考えられる", "と考えられた", "と思われる", "と推測", "と推定", "恐れがある",
    "おそれがある", "示唆", "らしい", "ようだ", "ようである", "疑い", "疑われる",
)  # fmt: skip
COMPLEX_CUES: tuple[str, ...] = (
    "ないとは言えない", "ないとはいえない", "ないわけではない", "ないわけではありません",
    "なくはない", "否定できない", "否定はできない", "否定し得ない", "言えなくもない",
    "なくもない", "ないこともない", "とは言えない", "とはいえない", "とは限らない",
)  # fmt: skip
# Words that contain ない/なく but are not negation ("few", "dangerous", "certainly", …).
NOT_NEGATION: tuple[str, ...] = (
    "少な", "危な", "足りな", "間違いな", "違いな", "欠かせな", "仕方な", "しかたな",
    "申し訳な", "絶え間な", "まもなく", "間もなく", "なくて", "ないし",
)  # fmt: skip
_CLAUSE_END = re.compile(r"[。！？!?]|が、|けれど|しかし|一方")


def _blank(text: str, phrases: tuple[str, ...] | list[str]) -> tuple[str, int]:
    """Replace each phrase with spaces (keeps offsets); returns new text and hit count."""
    hits = 0
    for p in sorted(phrases, key=len, reverse=True):
        if not p:
            continue
        while p in text:
            hits += 1
            text = text.replace(p, " " * len(p), 1)
    return text, hits


def negation_hedge(
    text: str,
    head: tuple[int, int],
    tail: tuple[int, int],
    sdoc: Any = None,
    extra_neg: list[str] | None = None,
    extra_hedge: list[str] | None = None,
) -> tuple[bool, bool, bool]:
    last = max(head[1], tail[1])
    scope = text[last:]
    m = _CLAUSE_END.search(scope)
    if m:
        scope = scope[: m.start()]
    scope, n_complex = _blank(scope, COMPLEX_CUES)
    if n_complex:
        return (False, False, True)
    scope, n_hedge = _blank(scope, [*HEDGE_CUES, *(extra_hedge or [])])
    scope, _ = _blank(scope, NOT_NEGATION)
    _, n_neg = _blank(scope, [*NEGATION_CUES, *(extra_neg or [])])
    if sdoc is not None and n_neg == 0 and sdoc.has_annotation("POS"):
        # GiNZA marks negation as the auxiliary ない/ず/ぬ (no Polarity feature).
        n_neg = sum(
            1
            for tok in sdoc
            if tok.idx >= last
            and tok.pos_ == "AUX"
            and tok.lemma_ in {"ない", "ず", "ぬ"}
            and not any(x in tok.text for x in NOT_NEGATION)
        )
    return (n_neg == 1, n_hedge > 0, n_neg >= 2)
