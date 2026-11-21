"""Trigger-lexicon relation stage.

Each rule lists trigger words for some relations and where the trigger must sit relative
to an ordered mention pair ``(a, b)``:

* ``between`` — ``a … trigger … b`` (English SVO: "X reduces Y")
* ``after``   — ``a … b … trigger`` (Japanese SOV: 「XはYを軽減する」)
* ``any``     — between, after, or just before ``a``

Distances are counted in the language profile's *units* (tokens for English, bunsetsu
for Japanese when GiNZA is available). ``order: reverse`` makes ``b`` the head.
Trigger hits are less certain than dependency hits; the validate stage scores them lower
and may flip their direction when only the flipped direction fits the schema.
"""

from __future__ import annotations

from bisect import bisect_right
from typing import Any, ClassVar

from leankg.domain.pack import TriggerRule
from leankg.models import Document, Mention, Sentence, Triple
from leankg.stages.base import BaseStage
from leankg.stages.preprocess import ensure_spacy_doc
from leankg.stages.relations.common import (
    find_phrase,
    new_triple,
    pairs,
    related_pairs,
    to_candidates,
)


class _Units:
    """Maps character offsets to unit indices."""

    def __init__(self, units: list[Any]) -> None:
        self.starts = [u.start_char for u in units] or [0]

    def at(self, char: int) -> int:
        return max(bisect_right(self.starts, char) - 1, 0)


class TriggerStage(BaseStage):
    name: ClassVar[str] = "trigger"

    def _hits(self, sent: Sentence, rule: TriggerRule, profile: Any) -> list[tuple[int, int]]:
        nt = profile.normalize_map(sent.text)
        hits = []
        for word in rule.words:
            key = profile.normalize(word)
            for i in find_phrase(nt.text, key):
                hits.append(nt.to_original(i, i + len(key)))
        return sorted(set(hits))

    def _fits(
        self, rule: TriggerRule, a: Mention, b: Mention, hit: tuple[int, int], units: _Units
    ) -> bool:
        ts, te = hit
        if rule.position in ("between", "any") and a.end <= ts and te <= b.start:
            return units.at(b.start) - units.at(max(a.end - 1, 0)) <= rule.window
        if rule.position in ("after", "any") and ts >= b.end:
            return units.at(ts) - units.at(max(b.end - 1, 0)) <= rule.window
        if rule.position == "any" and te <= a.start:
            return units.at(a.start) - units.at(ts) <= rule.window
        return False

    def _type_ok(self, rule: TriggerRule, a: Mention, b: Mention) -> bool:
        """Does some relation of the rule fit the types (either direction, as validate may flip)?"""
        pack = self.ctx.require_pack()
        return any(
            pack.relation_allowed(c.type, a.type, b.type)
            or pack.relation_allowed(c.type, b.type, a.type)
            for c in rule.relations
        )

    def find(self, doc: Document, sent: Sentence) -> list[Triple]:
        mentions = doc.mentions_in(sent.id)
        if len(mentions) < 2:
            return []
        rules = self.ctx.require_pack().relations_for(sent.lang).triggers
        if not rules:
            return []
        profile = self.ctx.get_profiles().get(sent.lang)
        units = _Units(profile.units(ensure_spacy_doc(self.ctx, sent)))
        hits = {rule.id: self._hits(sent, rule, profile) for rule in rules}
        done = related_pairs(doc, sent.id)
        out: list[Triple] = []
        for a, b in pairs(mentions):
            if frozenset((a.id, b.id)) in done:
                continue
            best: TriggerRule | None = None
            for rule in rules:
                if not any(self._fits(rule, a, b, h, units) for h in hits[rule.id]):
                    continue
                if not self._type_ok(rule, a, b):
                    continue
                if best is None or rule.weight > best.weight:
                    best = rule
            if best is None:
                continue
            head, tail = (a, b) if best.order == "forward" else (b, a)
            out.append(
                new_triple(
                    doc,
                    sent,
                    head,
                    tail,
                    "trigger",
                    to_candidates(best.relations),
                    weight=best.weight,
                    pattern_id=best.id,
                    allow_flip=True,
                )
            )
        return out

    def process(self, doc: Document) -> Document:
        for sent in doc.sentences():
            doc.triples.extend(self.find(doc, sent))
        return doc
