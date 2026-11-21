"""Corpus-level graph: merges entities and triples from many documents."""

from __future__ import annotations

from dataclasses import dataclass, field

from leankg.models import Alias, Document, Entity, Mention, Triple

MAX_PROVENANCE = 50


def _union(a: list[str], b: list[str]) -> list[str]:
    return sorted(set(a) | set(b))


@dataclass
class KnowledgeGraph:
    """Merged graph built from processed documents.

    Repeated evidence for the same ``(head, tail, type, negated)`` increments
    ``evidence_count`` and accumulates chunk ids, languages and provenance.
    """

    domain: str = ""
    documents: dict[str, Document] = field(default_factory=dict)
    entities: dict[str, Entity] = field(default_factory=dict)
    triples: dict[tuple[str, str, str, bool], Triple] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------ merge
    def add_document(self, doc: Document) -> None:
        self.documents[doc.id] = doc
        for ent in doc.entities:
            self._merge_entity(ent)
        for triple in doc.triples:
            if triple.head and triple.tail and triple.type:
                self._merge_triple(triple)

    def _merge_entity(self, ent: Entity) -> None:
        cur = self.entities.get(ent.id)
        if cur is None:
            self.entities[ent.id] = ent.model_copy(deep=True)
            return
        seen = {(a.text, a.lang) for a in cur.aliases}
        cur.aliases.extend(
            Alias(text=a.text, lang=a.lang) for a in ent.aliases if (a.text, a.lang) not in seen
        )
        cur.lang_seen = _union(cur.lang_seen, ent.lang_seen)
        cur.mention_count += ent.mention_count
        cur.confidence = max(cur.confidence, ent.confidence)
        cur.name_ja = cur.name_ja or ent.name_ja
        room = MAX_PROVENANCE - len(cur.provenance)
        if room > 0:
            cur.provenance.extend(ent.provenance[:room])

    def _merge_triple(self, t: Triple) -> None:
        cur = self.triples.get(t.key)
        if cur is None:
            new = t.model_copy(deep=True)
            new.chunk_ids = _union(new.chunk_ids, [p.chunk_id for p in new.provenance])
            new.doc_ids = _union(new.doc_ids, [p.doc_id for p in new.provenance])
            new.langs = _union(new.langs, [p.lang for p in new.provenance])
            self.triples[t.key] = new
            return
        cur.evidence_count += t.evidence_count
        cur.confidence = max(cur.confidence, t.confidence)
        cur.chunk_ids = _union(cur.chunk_ids, [*t.chunk_ids, *(p.chunk_id for p in t.provenance)])
        cur.doc_ids = _union(cur.doc_ids, [*t.doc_ids, *(p.doc_id for p in t.provenance)])
        cur.langs = _union(cur.langs, [*t.langs, *(p.lang for p in t.provenance)])
        cur.hedged = cur.hedged and t.hedged
        if _status_rank(t.status) > _status_rank(cur.status):
            cur.status = t.status
            cur.method = t.method
        room = MAX_PROVENANCE - len(cur.provenance)
        if room > 0:
            cur.provenance.extend(t.provenance[:room])

    # ---------------------------------------------------------------- queries
    def mentions(self) -> list[Mention]:
        return [m for d in self.documents.values() for m in d.mentions if m.entity_id]

    def facts(self, include_unverified: bool = False) -> list[Triple]:
        """Accepted (and negative) triples; optionally unverified candidates too."""
        keep = {"accepted", "negative"} | (
            {"unverified", "candidate"} if include_unverified else set()
        )
        return [t for t in self.triples.values() if t.status in keep]


def _status_rank(status: str) -> int:
    return {"rejected": 0, "candidate": 1, "unverified": 2, "negative": 3, "accepted": 4}[status]
