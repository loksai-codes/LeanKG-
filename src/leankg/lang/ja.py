"""JapaneseProfile. TODO: full implementation in M1."""

from __future__ import annotations

import unicodedata
from typing import Any


class JapaneseProfile:
    code = "ja"

    def load_nlp(self, model: str | None = None) -> Any:
        import spacy

        return spacy.blank("xx")

    def normalize(self, text: str) -> str:
        return unicodedata.normalize("NFKC", text).lower()

    def split_sentences(self, text: str) -> list[tuple[int, int]]:
        return [(0, len(text))] if text else []
