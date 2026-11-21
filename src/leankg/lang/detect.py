"""Cheap language detection: share of kana/CJK characters.

No extra dependency. A text whose non-space characters are more than ``threshold`` kana or
CJK ideographs is Japanese (``"ja"``), otherwise English (``"en"``). Chinese text would also
be classified ``"ja"``; that is accepted for v1 (only en/ja profiles exist).
"""

from __future__ import annotations

DEFAULT_THRESHOLD = 0.2

_RANGES: tuple[tuple[int, int], ...] = (
    (0x3040, 0x309F),  # hiragana
    (0x30A0, 0x30FF),  # katakana
    (0x31F0, 0x31FF),  # katakana phonetic extensions
    (0xFF66, 0xFF9F),  # half-width katakana
    (0x3400, 0x4DBF),  # CJK extension A
    (0x4E00, 0x9FFF),  # CJK unified ideographs
    (0xF900, 0xFAFF),  # CJK compatibility ideographs
)


def is_japanese_char(ch: str) -> bool:
    code = ord(ch)
    return any(lo <= code <= hi for lo, hi in _RANGES)


def cjk_ratio(text: str) -> float:
    """Share of kana/CJK characters among non-space, non-punctuation-ASCII characters."""
    considered = 0
    hits = 0
    for ch in text:
        if ch.isspace():
            continue
        if ch.isascii() and not ch.isalnum():
            continue
        considered += 1
        if is_japanese_char(ch):
            hits += 1
    return hits / considered if considered else 0.0


def detect_language(text: str, threshold: float = DEFAULT_THRESHOLD, default: str = "en") -> str:
    """Return ``"ja"`` or ``"en"`` (``default`` for empty text)."""
    if not text or not text.strip():
        return default
    return "ja" if cjk_ratio(text) > threshold else "en"
