"""English negation / hedging rules (negspaCy termsets used when installed)."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

NEGATION_CUES: tuple[str, ...] = (
    "not", "no", "never", "n't", "neither", "nor", "without", "cannot", "none",
    "failed to", "fail to", "fails to", "absence of", "no evidence", "unrelated to",
    "did not", "does not", "do not", "was not", "were not", "is not", "are not",
)  # fmt: skip
HEDGE_CUES: tuple[str, ...] = (
    "may", "might", "could", "possibly", "possible", "suggest", "suggests", "suggested",
    "likely", "potential", "potentially", "appear to", "appears to", "appeared to",
    "seem to", "seems to", "seemed to",
    "is thought", "hypothesized", "hypothesised", "presumably", "perhaps", "probably",
    "unclear", "uncertain", "putative", "suspected",
)  # fmt: skip
COMPLEX_CUES: tuple[str, ...] = (
    "cannot be ruled out", "can not be ruled out", "cannot be excluded", "not unlikely",
    "not impossible", "not without", "no longer", "not only",
)  # fmt: skip

_WORDS = re.compile(r"[a-z0-9]+(?=n't)|n't|[a-z0-9]+(?:-[a-z0-9]+)*")
_CLAUSE_BREAK = re.compile(r"[;:]|,\s+(?:but|whereas|while|although|however)\b")


@lru_cache(maxsize=1)
def negspacy_cues() -> tuple[str, ...]:
    """Preceding/following negation phrases from negspaCy's clinical termset, if installed."""
    try:
        from negspacy.termsets import termset
    except ImportError:
        return ()
    make: Any = termset  # negspaCy is untyped
    patterns: dict[str, list[str]] = make("en_clinical").get_patterns()
    cues = [*patterns.get("preceding_negations", []), *patterns.get("following_negations", [])]
    return tuple(sorted({c.lower() for c in cues}))


def _scope(text: str, first_start: int, last_end: int) -> str:
    """The clause around both mentions: a little before the first, a little after the last."""
    start = max(first_start - 40, 0)
    for m in _CLAUSE_BREAK.finditer(text, start, first_start):
        start = m.end()
    end = min(last_end + 30, len(text))
    m2 = _CLAUSE_BREAK.search(text, last_end, end)
    if m2:
        end = m2.start()
    stop = re.search(r"[.!?]", text[last_end:end])
    if stop:
        end = last_end + stop.start()
    return text[start:end].lower()


def _count(words: str, cues: tuple[str, ...] | list[str]) -> int:
    hits = 0
    for cue in cues:
        pattern = rf"(?:^| ){re.escape(cue.lower())}(?: |$)"
        hits += len(re.findall(pattern, words))
    return hits


def negation_hedge(
    text: str,
    head: tuple[int, int],
    tail: tuple[int, int],
    sdoc: Any = None,
    extra_neg: list[str] | None = None,
    extra_hedge: list[str] | None = None,
) -> tuple[bool, bool, bool]:
    first, last = min(head[0], tail[0]), max(head[1], tail[1])
    scope = _scope(text, first, last).replace("’", "'")
    words = " ".join(_WORDS.findall(scope))
    complex_ = _count(words, COMPLEX_CUES) > 0
    if complex_:
        return (False, False, True)
    neg_cues = list(dict.fromkeys([*NEGATION_CUES, *negspacy_cues(), *(extra_neg or [])]))
    single = [c for c in neg_cues if " " not in c]
    multi = [c for c in neg_cues if " " in c]
    # count each negation once: multi-word cues ("did not") contain single ones ("not")
    n_single = _count(words, single)
    n_multi_only = sum(
        1 for c in multi if _count(words, [c]) and not any(w in single for w in c.split())
    )
    neg_hits = n_single + n_multi_only
    hedged = _count(words, [*HEDGE_CUES, *(extra_hedge or [])]) > 0
    return (neg_hits == 1, hedged, neg_hits >= 2)
