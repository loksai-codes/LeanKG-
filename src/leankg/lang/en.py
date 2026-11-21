"""EnglishProfile: spaCy ``en_core_web_sm`` (blank fallback), rule sentence splitting."""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, ClassVar

from leankg.lang.text import NormText, collapse_spaces, normalize_with_map, spans_from_cuts

log = logging.getLogger(__name__)

DEFAULT_MODEL = "en_core_web_sm"

_ABBREVIATIONS = frozenset(
    {
        "e.g", "i.e", "etc", "vs", "dr", "mr", "mrs", "ms", "prof", "fig", "figs", "al",
        "approx", "no", "nos", "vol", "ref", "refs", "st", "jr", "sr", "inc", "ltd", "co",
        "corp", "dept", "est", "min", "max", "mg", "ml", "cf", "ca", "u.s", "u.k", "p",
    }
)  # fmt: skip
_BOUNDARY = re.compile(r"[.!?]+[\"')\]]*(?=\s+[\"'(\[]?[A-Z0-9])")
_PARAGRAPH = re.compile(r"\n\s*\n")
_BULLET_LINE = re.compile(r"\n(?=\s*(?:[-*•▪◦]|\d+[.)])\s)")


def _en_group(group: str, _prev: str) -> str:
    return unicodedata.normalize("NFKC", group).casefold()


class EnglishProfile:
    code = "en"
    dict_strategy = "phrase"  # spaCy PhraseMatcher on LOWER
    fuzzy_scorer = "wratio"  # rapidfuzz WRatio
    _nlp_cache: ClassVar[dict[str, Any]] = {}

    # ---------------------------------------------------------------- models
    def load_nlp(self, model: str | None = None) -> Any:
        """Load (and cache) the spaCy pipeline; falls back to ``spacy.blank("en")``."""
        name = model or DEFAULT_MODEL
        if name not in self._nlp_cache:
            import spacy

            try:
                nlp = spacy.load(name)
            except OSError:
                log.warning("spaCy model %r not installed; using a blank English tokenizer", name)
                nlp = spacy.blank("en")
            self._nlp_cache[name] = nlp
        return self._nlp_cache[name]

    # ---------------------------------------------------------- normalization
    def normalize_map(self, text: str) -> NormText:
        return normalize_with_map(text, _en_group)

    def normalize(self, text: str) -> str:
        """Matching key: NFKC, casefold, whitespace collapsed."""
        return collapse_spaces(self.normalize_map(text).text)

    def accept_dict_key(self, key: str) -> bool:
        return len(key) >= 2

    def term_variants(self, term: str) -> list[str]:
        """The term plus a simple plural of its last word (dictionary terms are singular)."""
        variants = [term]
        words = term.split(" ")
        last = words[-1]
        if not last or not last[-1].isalpha() or any(ch.isdigit() for ch in last):
            return variants
        lower = last.lower()
        if lower.endswith(("s", "x", "z", "ch", "sh")):
            plural = last + "es" if not lower.endswith("s") else last
        elif lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
            plural = last[:-1] + "ies"
        else:
            plural = last + "s"
        if plural != last:
            variants.append(" ".join([*words[:-1], plural]))
        return variants

    # -------------------------------------------------------------- sentences
    def split_sentences(self, text: str) -> list[tuple[int, int]]:
        """Rule-based splitter: ``.!?`` + capital, blank lines and bullet lines."""
        cuts: set[int] = set()
        for m in _PARAGRAPH.finditer(text):
            cuts.add(m.start())
        for m in _BULLET_LINE.finditer(text):
            cuts.add(m.start())
        for m in _BOUNDARY.finditer(text):
            before = text[: m.start()]
            word = re.search(r"([A-Za-z.]+)$", before)
            if word and word.group(1).lower().rstrip(".") in _ABBREVIATIONS:
                continue
            if word and len(word.group(1)) == 1 and word.group(1).isupper():
                continue  # initials such as "J. Smith"
            cuts.add(m.end())
        return spans_from_cuts(text, sorted(cuts))

    # ---------------------------------------------------- relation helpers
    def units(self, doc: Any) -> list[Any]:
        """Units used for trigger windows: tokens."""
        return [doc[i : i + 1] for i in range(len(doc))]

    def connected(self, doc: Any, a: Any, b: Any) -> bool | None:
        """English places no parse restriction on co-occurrence pairs."""
        return None

    def negation_hedge(
        self,
        text: str,
        head: tuple[int, int],
        tail: tuple[int, int],
        sdoc: Any = None,
        extra_neg: list[str] | None = None,
        extra_hedge: list[str] | None = None,
    ) -> tuple[bool, bool, bool]:
        """``(negated, hedged, complex)`` for a relation between two spans of ``text``."""
        from leankg.lang import en_rules

        return en_rules.negation_hedge(text, head, tail, sdoc, extra_neg, extra_hedge)
