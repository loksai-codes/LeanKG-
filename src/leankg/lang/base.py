"""LanguageProfile: the only place language-specific behaviour lives."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LanguageProfile(Protocol):
    """Everything a stage may need that depends on the language."""

    code: str

    def load_nlp(self, model: str | None = None) -> Any:
        """Return a (cached) spaCy ``Language`` for this language."""
        ...

    def normalize(self, text: str) -> str:
        """Matching key used for dictionary terms and text alike."""
        ...

    def split_sentences(self, text: str) -> list[tuple[int, int]]:
        """Character spans of sentences in ``text``."""
        ...


class ProfileRegistry:
    """Lazily creates and caches one profile per language code."""

    def __init__(self, models: dict[str, str] | None = None) -> None:
        self._profiles: dict[str, Any] = {}
        self.models = dict(models or {})

    def get(self, code: str) -> Any:
        if code not in self._profiles:
            self._profiles[code] = make_profile(code)
        return self._profiles[code]

    def register(self, profile: Any) -> None:
        self._profiles[profile.code] = profile

    def __contains__(self, code: str) -> bool:
        return code in self._profiles


def make_profile(code: str) -> Any:
    if code == "en":
        from leankg.lang.en import EnglishProfile

        return EnglishProfile()
    if code == "ja":
        from leankg.lang.ja import JapaneseProfile

        return JapaneseProfile()
    raise KeyError(f"no LanguageProfile for {code!r} (available: en, ja)")
