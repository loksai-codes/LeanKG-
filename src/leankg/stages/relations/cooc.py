"""Typed co-occurrence: low-confidence candidates for pairs the schema allows.

Only pairs whose types can be related (in either direction) are kept. Where the profile
can tell from the parse that two mentions are not connected (Japanese bunsetsu links),
the pair is skipped. These candidates are what the router later sends to the LLM when
no rule fired ("≥ 2 typed entities but no rule relation").
"""

from __future__ import annotations

from typing import ClassVar

from leankg.models import Document, RelationCandidate, Sentence, Triple
from leankg.stages.base import BaseStage
from leankg.stages.relations.common import mention_span, new_triple, pairs, related_pairs

MAX_PAIRS_PER_SENTENCE = 15


class CoocStage(BaseStage):
    name: ClassVar[str] = "cooc"

    def find(self, doc: Document, sent: Sentence) -> list[Triple]:
        mentions = doc.mentions_in(sent.id)
        if len(mentions) < 2:
            return []
        pack = self.ctx.require_pack()
        profile = self.ctx.get_profiles().get(sent.lang)
        sdoc = sent.spacy_doc
        done = related_pairs(doc, sent.id)
        out: list[Triple] = []
        for a, b in pairs(mentions):
            if len(out) >= MAX_PAIRS_PER_SENTENCE:
                break
            if frozenset((a.id, b.id)) in done:
                continue
            forward = pack.allowed_relations(a.type, b.type)
            backward = [r for r in pack.allowed_relations(b.type, a.type) if r not in forward]
            if not forward and not backward:
                continue
            if sdoc is not None:
                sa, sb = mention_span(sdoc, a), mention_span(sdoc, b)
                if sa is not None and sb is not None and profile.connected(sdoc, sa, sb) is False:
                    continue
            candidates = [RelationCandidate(type=r) for r in forward] + [
                RelationCandidate(type=r, reverse=True) for r in backward
            ]
            out.append(new_triple(doc, sent, a, b, "cooc", candidates))
        return out

    def process(self, doc: Document) -> Document:
        for sent in doc.sentences():
            doc.triples.extend(self.find(doc, sent))
        return doc
