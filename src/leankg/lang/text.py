"""Character-level normalization that keeps a map back to the original offsets.

Unicode NFKC can change string length (``ｶﾞ`` → ``ガ``, ``㎎`` → ``mg``), so every matcher
that works on normalized text needs a way back to the original characters. Text is cut
into *groups* (a base character plus following combining / voiced-sound marks), each group
is normalized on its own, and every output character remembers the original span of its
group.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

# Half-width voiced/semi-voiced sound marks and their combining forms.
_VOICED_MARKS = frozenset("ﾞﾟ゙゚")


@dataclass(frozen=True)
class NormText:
    """Normalized text plus, for each normalized char, its ``(start, end)`` in the original."""

    original: str
    text: str
    spans: tuple[tuple[int, int], ...]

    def to_original(self, start: int, end: int) -> tuple[int, int]:
        """Map a normalized ``[start, end)`` range to the original text."""
        if not self.spans:
            return (0, 0)
        if end <= start:
            pos = self.spans[min(start, len(self.spans) - 1)][0]
            return (pos, pos)
        return (self.spans[start][0], self.spans[end - 1][1])


def iter_groups(text: str) -> list[tuple[int, int]]:
    """Split ``text`` into (start, end) groups: base char + trailing combining marks."""
    groups: list[tuple[int, int]] = []
    i = 0
    n = len(text)
    while i < n:
        j = i + 1
        while j < n and (unicodedata.combining(text[j]) or text[j] in _VOICED_MARKS):
            j += 1
        groups.append((i, j))
        i = j
    return groups


GroupFn = Callable[[str, str], str]
"""Normalizes one group. Receives ``(group, previous_output_text)`` and returns output."""


def normalize_with_map(text: str, group_fn: GroupFn) -> NormText:
    out: list[str] = []
    spans: list[tuple[int, int]] = []
    for start, end in iter_groups(text):
        produced = group_fn(text[start:end], "".join(out[-1:]))
        for ch in produced:
            out.append(ch)
            spans.append((start, end))
    return NormText(original=text, text="".join(out), spans=tuple(spans))


def nfkc_group(group: str, _prev: str) -> str:
    return unicodedata.normalize("NFKC", group)


def nfkc_with_map(text: str) -> NormText:
    """Light normalization (NFKC only), used by regex matching."""
    return normalize_with_map(text, nfkc_group)


def collapse_spaces(text: str) -> str:
    return " ".join(text.split())


def spans_from_cuts(text: str, cuts: list[int]) -> list[tuple[int, int]]:
    """Turn sorted cut positions into whitespace-trimmed, non-empty ``(start, end)`` spans."""
    spans: list[tuple[int, int]] = []
    prev = 0
    for cut in [*sorted(set(cuts)), len(text)]:
        start, end = prev, cut
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if end > start:
            spans.append((start, end))
        prev = max(prev, cut)
    return spans
