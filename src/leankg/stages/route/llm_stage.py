"""LLM stage: resolve hard cases across all documents in one go, then apply the verdicts.

* Relations in a verdict become ``method="llm"`` triples (validated against the case's
  allowed types, scored with the ``llm`` prior × the model's confidence).
* Unconfirmed candidates of a resolved sentence are rejected (the LLM looked and said no).
* Cases skipped by the budget cap keep their candidates as ``unverified``.
* ``link_choice`` re-links an ambiguous mention.
* Usage, cache hits, dedupe hits and cost go into the RunReport, overall and per language.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, ClassVar

from leankg.llm.cache import VerdictCache
from leankg.llm.resolver import Resolver, ResolveResult, schema_version
from leankg.models import Document, HardCase, LLMVerdict, Provenance, RelationCandidate, Triple
from leankg.stages.base import BaseStage, StageContext
from leankg.stages.linking import build_entities

log = logging.getLogger(__name__)


class LLMStage(BaseStage):
    name: ClassVar[str] = "llm"

    def __init__(self, ctx: StageContext) -> None:
        super().__init__(ctx)
        self._resolver: Resolver | None = None

    def resolver(self) -> Resolver | None:
        client = self.ctx.llm
        if client is None or getattr(client, "name", "none") == "none":
            return None
        if self._resolver is None:
            cfg = self.config.llm
            pack = self.ctx.require_pack()
            if hasattr(client, "hints") and not client.hints:
                client.hints = pack.llm_hints
            cache = VerdictCache(cfg.cache_path) if cfg.use_cache else None
            rels = {k: v.model_dump(by_alias=True) for k, v in pack.ontology.relations.items()}
            self._resolver = Resolver(client, cfg, schema_version(rels), cache, cfg.log_path)
        return self._resolver

    # ------------------------------------------------------------------ apply
    def _apply(self, doc: Document, case: HardCase, verdict: LLMVerdict) -> None:
        mentions = doc.mention_index()
        sent = doc.sentence_index()[case.sent_id]
        sc = self.config.scoring
        if verdict.link_choice is not None and case.link_question is not None:
            m = mentions[case.entities[case.link_question.entity].mention_id]
            chosen = case.link_question.option_ids[verdict.link_choice]
            concept = self.ctx.require_pack().concepts.get(chosen)
            m.ontology_id = m.entity_id = chosen
            m.link_method, m.ambiguous = "llm", False
            if concept is not None:
                m.type = concept.type
        # drop open candidates in this sentence: the LLM has answered for it
        doc.triples = [
            t for t in doc.triples
            if not (t.sent_id == case.sent_id and t.status in ("candidate", "unverified"))
        ]  # fmt: skip
        existing = {(t.head_mention, t.tail_mention, t.type, t.negated) for t in doc.triples}
        for r in verdict.relations:
            head = mentions[case.entities[r.head].mention_id]
            tail = mentions[case.entities[r.tail].mention_id]
            if (head.id, tail.id, r.type, r.negated) in existing:
                continue
            conf = round(
                sc.prior("llm") * r.confidence * (sc.hedge_penalty if r.hedged else 1.0), 4
            )
            status = (
                "candidate"
                if conf < sc.accept_threshold
                else ("negative" if r.negated else "accepted")
            )
            t = Triple(
                id=f"{case.sent_id}:llm:{r.head}-{r.tail}:{r.type}",
                head_mention=head.id,
                tail_mention=tail.id,
                head=head.entity_id or "",
                tail=tail.entity_id or "",
                type=r.type,
                candidates=[RelationCandidate(type=r.type)],
                method="llm",
                confidence=conf,
                negated=r.negated,
                hedged=r.hedged,
                status="unverified" if status == "candidate" else status,
                doc_id=doc.id,
                sent_id=sent.id,
                chunk_ids=[sent.chunk_id],
                doc_ids=[doc.id],
                langs=[sent.lang],
                provenance=[
                    Provenance(
                        doc_id=doc.id,
                        chunk_id=sent.chunk_id,
                        sent_id=sent.id,
                        start=sent.start + min(head.start, tail.start),
                        end=sent.start + max(head.end, tail.end),
                        method="llm",
                        lang=sent.lang,
                        confidence=conf,
                        pattern_id=getattr(self.ctx.llm, "model", None),
                    )
                ],
            )
            doc.triples.append(t)
            existing.add((head.id, tail.id, r.type, r.negated))

    def _report(self, res: ResolveResult) -> None:
        report = self.ctx.report
        client: Any = self.ctx.llm
        usage = client.usage
        cfg = self.config.llm
        report.provider = getattr(client, "name", report.provider)
        report.model = getattr(client, "model", report.model)
        report.llm_requests = usage.requests
        report.tokens_in, report.tokens_out = usage.tokens_in, usage.tokens_out
        report.est_cost_usd = (
            usage.tokens_in * cfg.price_in_per_mtok + usage.tokens_out * cfg.price_out_per_mtok
        ) / 1e6
        report.budget_exhausted = report.budget_exhausted or res.budget_exhausted
        total_sent = sum(c.sent for c in res.by_lang.values()) or 1
        for lang, c in res.by_lang.items():
            stats = report.lang(lang)
            stats.llm_sentences += c.cases - c.budget_skipped - c.failed
            stats.cache_hits += c.cache_hits
            stats.dedupe_hits += c.dedupe_hits
            stats.budget_skipped += c.budget_skipped
            share = c.sent / total_sent
            stats.tokens_in = round(usage.tokens_in * share)
            stats.tokens_out = round(usage.tokens_out * share)
            stats.est_cost_usd = report.est_cost_usd * share
            report.llm_sentences += c.cases - c.budget_skipped - c.failed
            report.cache_hits += c.cache_hits
            report.dedupe_hits += c.dedupe_hits
            report.budget_skipped += c.budget_skipped
        for err in sorted(set(res.errors))[:5]:
            report.warnings.append(f"llm: {err}")

    # -------------------------------------------------------------- process
    def process_many(self, docs_in: Iterable[Document]) -> list[Document]:
        docs = list(docs_in)
        resolver = self.resolver()
        if resolver is None:
            return docs
        cases = [c for d in docs for c in d.hard_cases]
        if not cases:
            return docs
        res = resolver.resolve(cases)
        by_doc = {d.id: d for d in docs}
        touched: set[str] = set()
        for case in cases:
            verdict = res.verdicts.get(case.case_id)
            if verdict is None:
                continue
            self._apply(by_doc[case.doc_id], case, verdict)
            touched.add(case.doc_id)
        pack = self.ctx.require_pack()
        for doc_id in touched:
            doc = by_doc[doc_id]
            mentions = doc.mention_index()
            for t in doc.triples:  # links may have changed
                t.head = mentions[t.head_mention].entity_id or t.head
                t.tail = mentions[t.tail_mention].entity_id or t.tail
            doc.entities = build_entities(doc, pack)
        self._report(res)
        return docs

    def process(self, doc: Document) -> Document:
        return self.process_many([doc])[0]
