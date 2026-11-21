"""Router stage: decide which sentences are hard cases (docs/PLAN.md rules).

A sentence becomes a :class:`HardCase` when it has

* ≥ 2 typed entities that the schema allows to relate, but no rule relation
  (``no_rule_relation``),
* an ambiguous entity link (``ambiguous_link``),
* a rule triple below the accept threshold (``low_confidence``), or
* negation/hedging marked complex (``complex_negation``).

Never routed: sentences with no entities, or with a high-confidence rule hit. Setup D
(``route_all``) routes every sentence with ≥ 2 relatable entities instead.
"""

from __future__ import annotations

from typing import ClassVar

from leankg.models import (
    RULE_METHODS,
    AllowedRelation,
    Document,
    HardCase,
    HardCaseEntity,
    HardCaseReason,
    LinkQuestion,
    Mention,
    Sentence,
    Triple,
)
from leankg.stages.base import BaseStage


class RouteStage(BaseStage):
    name: ClassVar[str] = "route"

    def _reasons(self, mentions: list[Mention], triples: list[Triple]) -> list[HardCaseReason]:
        threshold = self.config.scoring.accept_threshold
        rule = [t for t in triples if t.method in RULE_METHODS]
        if any(t.status in ("accepted", "negative") and t.confidence >= threshold for t in rule):
            return []
        reasons: list[HardCaseReason] = []
        has_cooc = any(t.method == "cooc" for t in triples)
        if not rule and has_cooc:
            reasons.append(HardCaseReason.NO_RULE_RELATION)
        if any(m.ambiguous for m in mentions):
            reasons.append(HardCaseReason.AMBIGUOUS_LINK)
        if any(
            t.status == "candidate" and t.confidence < threshold and not t.complex for t in rule
        ):
            reasons.append(HardCaseReason.LOW_CONFIDENCE)
        if any(t.complex for t in triples):
            reasons.append(HardCaseReason.COMPLEX_NEGATION)
        return reasons

    def build_case(
        self, doc: Document, sent: Sentence, mentions: list[Mention], reasons: list[HardCaseReason]
    ) -> HardCase | None:
        pack = self.ctx.require_pack()
        # one entry per distinct entity, in text order
        chosen: list[Mention] = []
        seen: set[str] = set()
        for m in mentions:
            key = m.entity_id or m.id
            if key in seen:
                continue
            seen.add(key)
            chosen.append(m)
        allowed = []
        for i, a in enumerate(chosen):
            for j, b in enumerate(chosen):
                if i != j and (types := pack.allowed_relations(a.type, b.type)):
                    allowed.append(AllowedRelation(head=i, tail=j, types=types))
        question = None
        for i, m in enumerate(chosen):
            ids = [c.ontology_id for c in m.candidates if c.ontology_id]
            if m.ambiguous and len(set(ids)) > 1:
                labels = []
                for cid in dict.fromkeys(ids):
                    concept = pack.concepts.get(cid)
                    name = (
                        (concept.preferred(sent.lang) or concept.preferred("en"))
                        if concept
                        else None
                    )
                    labels.append(f"{name or cid} ({concept.type if concept else '?'})")
                question = LinkQuestion(
                    entity=i, options=labels, option_ids=list(dict.fromkeys(ids))
                )
                break
        if not allowed and question is None:
            return None
        return HardCase(
            case_id=f"{sent.id}:hc",
            doc_id=doc.id,
            sent_id=sent.id,
            lang=sent.lang,
            sentence=sent.text,
            entities=[
                HardCaseEntity(index=i, surface=m.text, type=m.type, mention_id=m.id)
                for i, m in enumerate(chosen)
            ],
            allowed=allowed,
            reasons=reasons,
            link_question=question,
        )

    def process(self, doc: Document) -> Document:
        route_all = bool(self.ctx.extras.get("route_all"))
        doc.hard_cases = []
        for sent in doc.sentences():
            mentions = doc.mentions_in(sent.id)
            if not mentions:
                continue
            triples = [t for t in doc.triples if t.sent_id == sent.id]
            if route_all:
                distinct = {m.entity_id or m.id for m in mentions}
                reasons = [HardCaseReason.ROUTE_ALL] if len(distinct) >= 2 else []
            else:
                reasons = self._reasons(mentions, triples)
            if not reasons:
                continue
            case = self.build_case(doc, sent, mentions, reasons)
            if case is not None:
                doc.hard_cases.append(case)
        # Without an LLM verdict, open candidates stay in the output flagged as unverified.
        for t in doc.triples:
            if t.status == "candidate":
                t.status = "unverified"
        return doc
