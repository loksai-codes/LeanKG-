"""Entity stages, cheapest first: dictionary → regex → NER → GLiNER."""

from leankg.stages.entities.dictionary import DictionaryStage
from leankg.stages.entities.regex import RegexStage

__all__ = ["DictionaryStage", "RegexStage"]
