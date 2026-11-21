"""Validate & score stage.

For every candidate triple:

1. pick the first relation candidate the schema allows for the (head, tail) types —
   ``reverse`` candidates swap head and tail; trigger hits may also be flipped (penalty);
2. drop schema violations and self-loops;
3. confidence = method prior × pattern weight × hedge/complex/flip penalties (config);
4. status: ``negative`` (negated, kept as negative evidence), ``accepted`` (confident),
   or ``candidate`` (to the router);
5. merge duplicates within the document (``evidence_count``), keeping the strongest
   method per mention pair; attach provenance.
"""

from __future__ import annotations

from typing import ClassVar

from leankg.models import Document, Mention, Provenance, Sentence, Triple
from leankg.stages.base import BaseStage
from leankg.stages.relations.common import METHOD_RANK

GENERIC_RELATIONS = frozenset({"ASSOCIATED_WITH", "RELATED_TO"})


class ValidateStage(BaseStage):
    name: ClassVar[str] = "validate"

    def _resolve(self, t: Triple, mentions: dict[str, Mention]) -> bool:
        """Choose relation + direction. Returns False if nothing fits the schema."""
        pack = self.ctx.require_pack()
        h, tl = mentions[t.head_mention], mentions[t.tail_mention]
        valid: list[tuple[str, Mention, Mention, bool]] = []
        for cand in t.candidates:
            head, tail = (tl, h) if cand.reverse else (h, tl)
            if pack.relation_allowed(cand.type, head.type, tail.type):
                valid.append((cand.type, head, tail, False))
        if not valid and t.allow_flip:
            for cand in t.candidates:
                head, tail = (h, tl) if cand.reverse else (tl, h)
                if pack.relation_allowed(cand.type, head.type, tail.type):
                    valid.append((cand.type, head, tail, True))
        if not valid:
            return False
        if t.method == "cooc":
            specific = [v for v in valid if v[0] not in GENERIC_RELATIONS]
            valid = specific or valid
        rel, head, tail, flipped = valid[0]
        t.type = rel
        t.head_mention, t.tail_mention = head.id, tail.id
        t.head, t.tail = head.entity_id or "", tail.entity_id or ""
        if flipped:
            t.weight *= self.config.scoring.flip_penalty
        # keep only the still-valid options (the router offers them to the LLM)
        t.candidates = [c for c in t.candidates if any(c.type == v[0] for v in valid)]
        return True

    def _score(self, t: Triple) -> None:
        sc = self.config.scoring
        conf = sc.prior(t.method) * t.weight
        if t.hedged:
            conf *= sc.hedge_penalty
        if t.complex:
            conf *= sc.complex_penalty
        t.confidence = round(min(conf, 1.0), 4)
        if t.complex or t.confidence < sc.accept_threshold:
            t.status = "candidate"
        elif t.negated:
            t.status = "negative"
        else:
            t.status = "accepted"

    @staticmethod
    def _provenance(t: Triple, head: Mention, tail: Mention, sent: Sentence) -> None:
        start = sent.start + min(head.start, tail.start)
        end = sent.start + max(head.end, tail.end)
        t.provenance = [
            Provenance(
                doc_id=t.doc_id,
                chunk_id=sent.chunk_id,
                sent_id=sent.id,
                start=start,
                end=end,
                method=t.method,
                lang=sent.lang,
                confidence=t.confidence,
                pattern_id=t.pattern_id,
            )
        ]
        t.chunk_ids = [sent.chunk_id]
        t.doc_ids = [t.doc_id]
        t.langs = [sent.lang]

    def process(self, doc: Document) -> Document:
        if not doc.triples:
            return doc
        mentions = doc.mention_index()
        sentences = doc.sentence_index()
        best_per_pair: dict[frozenset[str], Triple] = {}
        for t in doc.triples:
            if t.status in ("accepted", "negative") and t.type:
                # already validated (e.g. re-run) or produced by the LLM stage
                best_per_pair.setdefault(frozenset((t.head_mention, t.tail_mention)), t)
                continue
            if t.head_mention not in mentions or t.tail_mention not in mentions:
                continue
            if not self._resolve(t, mentions):
                continue
            if t.head == t.tail:
                continue
            self._score(t)
            self._provenance(t, mentions[t.head_mention], mentions[t.tail_mention],
                             sentences[t.sent_id])  # fmt: skip
            pair = frozenset((t.head_mention, t.tail_mention))
            cur = best_per_pair.get(pair)
            if cur is None or (METHOD_RANK.get(t.method, 0), t.confidence) > (
                METHOD_RANK.get(cur.method, 0),
                cur.confidence,
            ):
                best_per_pair[pair] = t
        # merge duplicates (same entities, relation and polarity) within the document
        merged: dict[tuple[str, str, str, bool], Triple] = {}
        for t in best_per_pair.values():
            cur = merged.get(t.key)
            if cur is None:
                merged[t.key] = t
                continue
            cur.evidence_count += t.evidence_count
            cur.provenance.extend(t.provenance)
            cur.chunk_ids = sorted({*cur.chunk_ids, *t.chunk_ids})
            cur.langs = sorted({*cur.langs, *t.langs})
            if t.confidence > cur.confidence:
                cur.confidence, cur.status, cur.method = t.confidence, t.status, t.method
        doc.triples = list(merged.values())
        return doc


__all__ = ["ValidateStage"]
