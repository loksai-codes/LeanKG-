"""Turn leankg output into gold-shaped examples (for Label Studio pre-annotation)."""

from __future__ import annotations

from leankg.eval.gold import GoldEntity, GoldExample, GoldRelation
from leankg.eval.metrics import prediction_from_doc
from leankg.models import Document


def doc_to_example(doc: Document, lang: str, ex_id: str) -> GoldExample:
    pred = prediction_from_doc(doc)
    mentions = sorted(
        {(m.start, m.end, m.type) for m in pred.mentions}, key=lambda x: (x[0], -x[1])
    )
    entities: list[GoldEntity] = []
    for s, e, t in mentions:
        if entities and s < entities[-1].end:
            continue
        entities.append(GoldEntity(start=s, end=e, text=doc.text[s:e], type=t))
    spans = {(e.start, e.end): i for i, e in enumerate(entities)}
    relations = []
    for r in pred.relations:
        hi, ti = spans.get(r.head), spans.get(r.tail)
        if hi is not None and ti is not None and hi != ti:
            relations.append(GoldRelation(head=hi, tail=ti, type=r.type, negated=r.negated))
    return GoldExample(id=ex_id, lang=lang, text=doc.text, entities=entities,
                       relations=relations, source="leankg-preannotation")  # fmt: skip


def preannotate(texts: list[str], domain: str, lang: str, setup: str = "B") -> list[GoldExample]:
    from leankg.pipeline import Pipeline

    pipe = Pipeline.from_domain(domain, setup=setup, llm="none")
    docs = pipe.run([Document(id=f"pre-{i}", text=t, lang=lang) for i, t in enumerate(texts)])
    return [doc_to_example(d, lang, d.id) for d in docs]
