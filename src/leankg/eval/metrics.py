"""Entity, linking and relation metrics against gold examples."""

from __future__ import annotations

from dataclasses import dataclass, field

from pydantic import BaseModel

from leankg.eval.gold import GoldExample
from leankg.models import Document

SYMMETRIC_DEFAULT = frozenset({"ASSOCIATED_WITH"})


class PRF(BaseModel):
    tp: int = 0
    fp: int = 0
    fn: int = 0

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0

    def add(self, other: PRF) -> None:
        self.tp += other.tp
        self.fp += other.fp
        self.fn += other.fn

    def summary(self) -> dict[str, float | int]:
        return {
            "tp": self.tp,
            "fp": self.fp,
            "fn": self.fn,
            "precision": round(self.precision, 4),
            "recall": round(self.recall, 4),
            "f1": round(self.f1, 4),
        }


@dataclass
class PredMention:
    start: int
    end: int
    type: str
    ontology_id: str | None


@dataclass
class PredRelation:
    head: tuple[int, int]
    tail: tuple[int, int]
    type: str
    negated: bool


@dataclass
class Prediction:
    mentions: list[PredMention] = field(default_factory=list)
    relations: list[PredRelation] = field(default_factory=list)


def prediction_from_doc(doc: Document) -> Prediction:
    """Document-level char offsets for mentions and fact triples (accepted/negative)."""
    sents = doc.sentence_index()
    chunks = doc.chunk_index()

    def offset(sent_id: str) -> int:
        s = sents[sent_id]
        return chunks[s.chunk_id].start + s.start

    pred = Prediction()
    spans: dict[str, tuple[int, int]] = {}
    for m in doc.mentions:
        off = offset(m.sent_id)
        spans[m.id] = (off + m.start, off + m.end)
        pred.mentions.append(PredMention(off + m.start, off + m.end, m.type, m.ontology_id))
    for t in doc.triples:
        if t.status not in ("accepted", "negative"):
            continue
        if t.head_mention in spans and t.tail_mention in spans:
            pred.relations.append(
                PredRelation(spans[t.head_mention], spans[t.tail_mention], t.type, t.negated)
            )
    return pred


def _overlap(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def entity_scores(gold: GoldExample, pred: Prediction) -> tuple[PRF, PRF]:
    """(exact, partial). Exact = same span and type; partial = overlapping span, same type."""
    exact, partial = PRF(), PRF()
    gold_keys = {(e.start, e.end, e.type) for e in gold.entities}
    pred_keys = {(m.start, m.end, m.type) for m in pred.mentions}
    exact.tp = len(gold_keys & pred_keys)
    exact.fp = len(pred_keys - gold_keys)
    exact.fn = len(gold_keys - pred_keys)
    used: set[int] = set()
    for g in gold.entities:
        hit = next(
            (
                i
                for i, m in enumerate(pred.mentions)
                if i not in used
                and m.type == g.type
                and _overlap((m.start, m.end), (g.start, g.end))
            ),
            None,
        )
        if hit is None:
            partial.fn += 1
        else:
            used.add(hit)
            partial.tp += 1
    partial.fp = len(pred.mentions) - len(used)
    return exact, partial


def linking_counts(gold: GoldExample, pred: Prediction) -> tuple[int, int]:
    """(correct, total) over gold entities with an id and an exactly matching mention."""
    by_span = {(m.start, m.end): m for m in pred.mentions}
    correct = total = 0
    for g in gold.entities:
        if not g.id:
            continue
        m = by_span.get((g.start, g.end))
        if m is None:
            continue
        total += 1
        correct += int(m.ontology_id == g.id)
    return correct, total


def relation_scores(
    gold: GoldExample, pred: Prediction, symmetric: frozenset[str] = SYMMETRIC_DEFAULT
) -> PRF:
    """A predicted relation matches a gold one when both argument spans overlap the gold
    arguments (in order, or either order for symmetric relations), the type is the same and
    the negation flag agrees. Each gold relation is matched at most once."""
    prf = PRF()
    gold_rels = [
        (
            (gold.entities[r.head].start, gold.entities[r.head].end),
            (gold.entities[r.tail].start, gold.entities[r.tail].end),
            r.type,
            r.negated,
        )
        for r in gold.relations
    ]
    used: set[int] = set()
    for p in pred.relations:
        match = None
        for i, (gh, gt, gtype, gneg) in enumerate(gold_rels):
            if i in used or gtype != p.type or gneg != p.negated:
                continue
            forward = _overlap(p.head, gh) and _overlap(p.tail, gt)
            backward = p.type in symmetric and _overlap(p.head, gt) and _overlap(p.tail, gh)
            if forward or backward:
                match = i
                break
        if match is None:
            prf.fp += 1
        else:
            used.add(match)
            prf.tp += 1
    prf.fn = len(gold_rels) - len(used)
    return prf
