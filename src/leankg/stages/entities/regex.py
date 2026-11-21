"""Regex entity stage: per-language patterns from ``patterns/entities.jsonl``.

Patterns run on NFKC-normalized sentence text (so ``５ｍｇ`` and ``Ｅ－１２３４`` match ASCII
patterns) and matches are mapped back to the original offsets.
"""

from __future__ import annotations

from typing import ClassVar

from leankg.lang.text import nfkc_with_map
from leankg.models import Document, Mention
from leankg.stages.base import BaseStage
from leankg.stages.entities.common import add_mentions, longest_non_overlapping, make_mention


class RegexStage(BaseStage):
    name: ClassVar[str] = "regex"

    def process(self, doc: Document) -> Document:
        pack = self.ctx.require_pack()
        prior = self.config.scoring.prior("regex")
        new: list[Mention] = []
        for sent in doc.sentences():
            patterns = pack.patterns_for(sent.lang)
            if not patterns:
                continue
            profile = self.ctx.get_profiles().get(sent.lang)
            nt = nfkc_with_map(sent.text)
            hits: list[tuple[int, int, int]] = []
            for k, pat in enumerate(patterns):
                for m in pat.regex.finditer(nt.text):
                    s, e = m.span(pat.group)
                    if e > s:
                        hits.append((s, e, k))
            for s, e, k in longest_non_overlapping(hits):
                pat = patterns[k]
                start, end = nt.to_original(s, e)
                new.append(
                    make_mention(
                        doc,
                        sent,
                        start,
                        end,
                        pat.type,
                        "regex",
                        pat.confidence if pat.confidence is not None else prior,
                        normalized=profile.normalize(sent.text[start:end]),
                        ontology_id=pat.ontology_id,
                        pattern_id=pat.id,
                    )
                )
        add_mentions(doc, new)
        return doc
