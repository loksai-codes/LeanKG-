"""Preprocess stage: run each chunk's language pipeline (spaCy / GiNZA) on its sentences."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, ClassVar

from leankg.models import Document, Sentence
from leankg.stages.base import BaseStage, StageContext


def model_for(ctx: StageContext, lang: str) -> str | None:
    if ctx.pack is not None:
        return ctx.pack.models.spacy.get(lang)
    return None


def nlp_for(ctx: StageContext, lang: str) -> Any:
    return ctx.get_profiles().get(lang).load_nlp(model_for(ctx, lang))


def ensure_spacy_doc(ctx: StageContext, sentence: Sentence) -> Any:
    """The sentence's spaCy doc, tokenizing on demand if preprocess was skipped."""
    if sentence.spacy_doc is None:
        sentence.set_spacy_doc(nlp_for(ctx, sentence.lang).make_doc(sentence.text))
    return sentence.spacy_doc


class PreprocessStage(BaseStage):
    name: ClassVar[str] = "preprocess"
    batch_size: ClassVar[int] = 64

    def process(self, doc: Document) -> Document:
        by_lang: dict[str, list[Sentence]] = defaultdict(list)
        for sent in doc.sentences():
            if sent.spacy_doc is None:
                by_lang[sent.lang].append(sent)
        for lang, sents in by_lang.items():
            nlp = nlp_for(self.ctx, lang)
            for sent, sdoc in zip(
                sents, nlp.pipe((s.text for s in sents), batch_size=self.batch_size), strict=True
            ):
                sent.set_spacy_doc(sdoc)
        return doc


__all__ = ["PreprocessStage", "ensure_spacy_doc", "nlp_for"]
