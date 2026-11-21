"""Negation / hedging stage.

The language profile decides (``profile.negation_hedge``): English uses cue lists (from
negspaCy's termsets when the ``[med]`` extra is installed, otherwise a built-in rule set);
Japanese uses the rules in docs/JAPANESE.md §7. Packs may add cues in
``patterns/relations.<lang>.yaml`` (``negation_cues`` / ``hedge_cues``).
"""

from __future__ import annotations

from typing import ClassVar

from leankg.models import Document
from leankg.stages.base import BaseStage


class NegationStage(BaseStage):
    name: ClassVar[str] = "negation"

    def process(self, doc: Document) -> Document:
        if not doc.triples:
            return doc
        pack = self.ctx.require_pack()
        mentions = doc.mention_index()
        sentences = doc.sentence_index()
        for t in doc.triples:
            head, tail = mentions.get(t.head_mention), mentions.get(t.tail_mention)
            sent = sentences.get(t.sent_id)
            if head is None or tail is None or sent is None:
                continue
            profile = self.ctx.get_profiles().get(sent.lang)
            extra = pack.relations_for(sent.lang)
            neg, hedge, cplx = profile.negation_hedge(
                sent.text,
                (head.start, head.end),
                (tail.start, tail.end),
                sent.spacy_doc,
                extra.negation_cues,
                extra.hedge_cues,
            )
            t.negated, t.hedged, t.complex = neg, hedge, cplx
        return doc
