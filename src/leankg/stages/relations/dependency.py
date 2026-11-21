"""Dependency-pattern relation stage (spaCy ``DependencyMatcher``).

Patterns are pack data (``patterns/relations.<lang>.yaml``). Each pattern names two anchor
nodes (``head`` and ``tail`` by default); the tokens matched there are mapped to mentions,
including coordinated tokens ("X causes A and B" → two triples).
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from leankg.domain.pack import DepPattern
from leankg.models import Document, Sentence, Triple
from leankg.stages.base import BaseStage, StageContext
from leankg.stages.preprocess import nlp_for
from leankg.stages.relations.common import new_triple, to_candidates, token_mention, with_conjuncts

log = logging.getLogger(__name__)


class DependencyStage(BaseStage):
    name: ClassVar[str] = "dependency"

    def __init__(self, ctx: StageContext) -> None:
        super().__init__(ctx)
        self._matchers: dict[str, tuple[Any, dict[str, DepPattern]] | None] = {}

    def _matcher(self, lang: str) -> tuple[Any, dict[str, DepPattern]] | None:
        if lang not in self._matchers:
            patterns = self.ctx.require_pack().relations_for(lang).dependency
            if not patterns:
                self._matchers[lang] = None
                return None
            from spacy.matcher import DependencyMatcher

            nlp = nlp_for(self.ctx, lang)
            matcher = DependencyMatcher(nlp.vocab, validate=True)
            by_id: dict[str, DepPattern] = {}
            for p in patterns:
                try:
                    matcher.add(p.id, [p.pattern])
                except ValueError as exc:
                    raise ValueError(f"relations.{lang}.yaml pattern {p.id}: {exc}") from exc
                by_id[p.id] = p
            self._matchers[lang] = (matcher, by_id)
        return self._matchers[lang]

    def find(self, doc: Document, sent: Sentence) -> list[Triple]:
        sdoc = sent.spacy_doc
        if sdoc is None or not sdoc.has_annotation("DEP"):
            return []
        mentions = doc.mentions_in(sent.id)
        if len(mentions) < 2:
            return []
        compiled = self._matcher(sent.lang)
        if compiled is None:
            return []
        matcher, by_id = compiled
        out: list[Triple] = []
        seen: set[tuple[str, str, str]] = set()
        for match_id, token_ids in matcher(sdoc):
            pat = by_id[sdoc.vocab.strings[match_id]]
            names = [node["RIGHT_ID"] for node in pat.pattern]
            anchors = dict(zip(names, token_ids, strict=True))
            if pat.head not in anchors or pat.tail not in anchors:
                continue
            for h_tok in with_conjuncts(sdoc[anchors[pat.head]]):
                for t_tok in with_conjuncts(sdoc[anchors[pat.tail]]):
                    head = token_mention(h_tok, mentions)
                    tail = token_mention(t_tok, mentions)
                    if head is None or tail is None or head.id == tail.id:
                        continue
                    key = (head.id, tail.id, pat.id)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(
                        new_triple(
                            doc,
                            sent,
                            head,
                            tail,
                            "dep",
                            to_candidates(pat.relations),
                            weight=pat.weight,
                            pattern_id=pat.id,
                        )
                    )
        return out

    def process(self, doc: Document) -> Document:
        for sent in doc.sentences():
            doc.triples.extend(self.find(doc, sent))
        return doc
