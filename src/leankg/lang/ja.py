"""JapaneseProfile: GiNZA ``ja_ginza`` with a dependency-free fallback.

Normalization (docs/JAPANESE.md §3): NFKC → hiragana→katakana → drop long-vowel marks
that follow kana → lowercase Latin. The same function is applied to dictionary terms and
text, so ひずみ/ヒズミ and ﾓｰﾀｰ/モーター match.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from typing import Any, ClassVar

from leankg.lang.text import NormText, collapse_spaces, normalize_with_map, spans_from_cuts

log = logging.getLogger(__name__)

DEFAULT_MODEL = "ja_ginza"

_LONG_VOWEL_MARKS = frozenset("ー‐―−-~〜ｰ")
_TERMINATORS = "。！？!?．"
_CLOSERS = "」』）)】〉》\"'”’"
_SENT_END = re.compile(rf"[{re.escape(_TERMINATORS)}]+[{re.escape(_CLOSERS)}]*|\n+")


def _is_kana(ch: str) -> bool:
    return "ぁ" <= ch <= "ヿ" and ch not in "・ー"


def hira2kata(text: str) -> str:
    """Hiragana → katakana (uses jaconv when installed; identical result)."""
    try:
        import jaconv

        return str(jaconv.hira2kata(text))
    except ImportError:  # pragma: no cover - exercised when the [ja] extra is absent
        return "".join(chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in text)


def _ja_group(group: str, prev: str) -> str:
    out = unicodedata.normalize("NFKC", group)
    if out in _LONG_VOWEL_MARKS and prev and _is_kana(prev):
        return ""
    return hira2kata(out).lower()


# ------------------------------------------------------------------ tokenizer
def _script(ch: str) -> str:
    if "ぁ" <= ch <= "ゟ":
        return "hira"
    if "゠" <= ch <= "ヿ" or "ｦ" <= ch <= "ﾟ":
        return "kata"
    if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿" or ch in "々〆":
        return "kanji"
    if ch.isdigit():
        return "digit"
    if ch.isalpha():
        return "latin"
    if ch.isspace():
        return "space"
    return "other"


class ScriptRunTokenizer:
    """Fallback tokenizer: one token per run of the same script (no dictionary)."""

    def __init__(self, vocab: Any) -> None:
        self.vocab = vocab

    def __call__(self, text: str) -> Any:
        from spacy.tokens import Doc

        words: list[str] = []
        spaces: list[bool] = []
        i = 0
        n = len(text)
        while i < n:
            kind = _script(text[i])
            j = i + 1
            if kind == "space":
                while j < n and _script(text[j]) == "space":
                    j += 1
                if words:
                    spaces[-1] = text[i:j] == " "
                    if text[i:j] != " ":
                        words.append(text[i:j])
                        spaces.append(False)
                else:
                    words.append(text[i:j])
                    spaces.append(False)
                i = j
                continue
            if kind != "other":
                while j < n and (_script(text[j]) == kind or (kind == "kata" and text[j] in "ーｰ")):
                    j += 1
            words.append(text[i:j])
            spaces.append(False)
            i = j
        return Doc(self.vocab, words=words, spaces=spaces)


class JapaneseProfile:
    code = "ja"
    dict_strategy = "chars"  # Aho-Corasick on normalized characters
    fuzzy_scorer = "ratio"  # fuzz.ratio on characters (token scorers suit spaced text only)
    _nlp_cache: ClassVar[dict[str, Any]] = {}

    def load_nlp(self, model: str | None = None) -> Any:
        """Load GiNZA; without the ``[ja]`` extra, a script-run tokenizer (no parse)."""
        name = model or DEFAULT_MODEL
        if name not in self._nlp_cache:
            import spacy

            try:
                nlp = spacy.load(name)
            except (OSError, ImportError):
                log.warning(
                    "spaCy model %r not installed (pip install 'leankg[ja]'); "
                    "using a script-run tokenizer without dependency parse",
                    name,
                )
                nlp = spacy.blank("xx")
                nlp.tokenizer = ScriptRunTokenizer(nlp.vocab)
            self._nlp_cache[name] = nlp
        return self._nlp_cache[name]

    # ---------------------------------------------------------- normalization
    def normalize_map(self, text: str) -> NormText:
        return normalize_with_map(text, _ja_group)

    def normalize(self, text: str) -> str:
        return collapse_spaces(self.normalize_map(text).text)

    def term_variants(self, term: str) -> list[str]:
        return [term]

    def accept_dict_key(self, key: str) -> bool:
        """Single characters only when they are kanji (錆, 煙); single kana are too ambiguous."""
        return len(key) >= 2 or (len(key) == 1 and _script(key) == "kanji")

    # -------------------------------------------------------------- sentences
    def split_sentences(self, text: str) -> list[tuple[int, int]]:
        """Split after 。！？!?． (keeping closing brackets) and on newlines."""
        return spans_from_cuts(text, [m.end() for m in _SENT_END.finditer(text)])

    # ---------------------------------------------------- relation helpers
    def bunsetsu(self, doc: Any) -> list[Any]:
        if doc.has_annotation("DEP"):
            try:
                import ginza

                return list(ginza.bunsetu_spans(doc))
            except (ImportError, KeyError, ValueError, AttributeError):
                return []
        return []

    def units(self, doc: Any) -> list[Any]:
        """Units for trigger windows: bunsetsu when GiNZA is available, else tokens."""
        spans = self.bunsetsu(doc)
        return spans or [doc[i : i + 1] for i in range(len(doc))]

    def connected(self, doc: Any, a: Any, b: Any) -> bool | None:
        """True if the bunsetsu of spans ``a`` and ``b`` are linked in the parse.

        Linked = one bunsetsu depends on the other, or both depend on the same bunsetsu
        (e.g. two arguments of one predicate). ``None`` when there is no parse.
        """
        units = self.bunsetsu(doc)
        if not units:
            return None

        def unit_of(token_i: int) -> int | None:
            for k, unit in enumerate(units):
                if unit.start <= token_i < unit.end:
                    return k
            return None

        def head_unit(k: int) -> int | None:
            unit = units[k]
            for tok in unit:
                if not (unit.start <= tok.head.i < unit.end):
                    return unit_of(tok.head.i)
            return None

        ua, ub = unit_of(a.root.i), unit_of(b.root.i)
        if ua is None or ub is None:
            return None
        if ua == ub:
            return True
        ha, hb = head_unit(ua), head_unit(ub)
        return ha == ub or hb == ua or (ha is not None and ha == hb)

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
        from leankg.lang import ja_rules

        return ja_rules.negation_hedge(text, head, tail, sdoc, extra_neg, extra_hedge)

    def trigger_phrase(
        self, text: str, first: tuple[int, int], second: tuple[int, int]
    ) -> tuple[str, str] | None:
        """A candidate trigger: the predicate after the second span (SOV), without the
        leading particle and trailing auxiliaries, e.g. 「を軽減した」 → 「軽減」."""
        rest = text[second[1] :]
        rest = re.split(r"[。！？!?、]", rest, maxsplit=1)[0]
        rest = re.sub(r"^(?:を|が|は|に|で|の|と|へ|も)+", "", rest)
        rest = re.sub(
            r"(?:させる|させた|している|していた|しない|しなかった|された|される|"
            r"した|する|します|しました|である|です|だ|ない|なかった)$",
            "",
            rest,
        )
        rest = rest.strip()
        if not 1 <= len(rest) <= 8:
            return None
        return rest, "after"
