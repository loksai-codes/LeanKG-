"""Entity stages, cheapest first: dictionary → regex → NER → GLiNER."""

from leankg.stages.entities.dictionary import DictionaryStage
from leankg.stages.entities.gliner_stage import GlinerStage
from leankg.stages.entities.ner import NerStage
from leankg.stages.entities.regex import RegexStage

__all__ = ["DictionaryStage", "GlinerStage", "NerStage", "RegexStage"]
