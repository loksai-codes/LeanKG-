"""Flat row views of a :class:`KnowledgeGraph`, shared by every exporter."""

from __future__ import annotations

import json
from typing import Any

from leankg.graph import KnowledgeGraph
from leankg.models import Entity, Triple


def document_rows(g: KnowledgeGraph) -> list[dict[str, Any]]:
    return [
        {
            "id": d.id,
            "title": d.title,
            "source": d.source,
            "url": d.url,
            "date": d.date,
            "lang": d.lang,
            "domain": g.domain,
        }
        for d in g.documents.values()
    ]


def chunk_rows(g: KnowledgeGraph, with_embedding: bool = True) -> list[dict[str, Any]]:
    rows = []
    for d in g.documents.values():
        for c in d.chunks:
            row: dict[str, Any] = {
                "id": c.id,
                "doc_id": d.id,
                "index": c.index,
                "text": c.text,
                "lang": c.lang,
                "start": c.start,
                "end": c.end,
            }
            if with_embedding and c.embedding is not None:
                row["embedding"] = c.embedding
            rows.append(row)
    return rows


def entity_row(e: Entity) -> dict[str, Any]:
    aliases_en = e.aliases_for("en")
    aliases_ja = e.aliases_for("ja")
    return {
        "id": e.id,
        "type": e.type,
        "name": e.name,
        "name_ja": e.name_ja,
        "aliases_en": aliases_en,
        "aliases_ja": aliases_ja,
        "aliases_text": " | ".join([*aliases_en, *aliases_ja]),
        "ontology_id": e.ontology_id,
        "domain": e.domain,
        "lang_seen": e.lang_seen,
        "mention_count": e.mention_count,
        "confidence": round(e.confidence, 4),
    }


def entity_rows(g: KnowledgeGraph) -> list[dict[str, Any]]:
    return [entity_row(e) for e in g.entities.values()]


def mention_rows(g: KnowledgeGraph) -> list[dict[str, Any]]:
    rows = []
    for d in g.documents.values():
        sents = d.sentence_index()
        for m in d.mentions:
            if not m.entity_id:
                continue
            sent = sents.get(m.sent_id)
            off = sent.start if sent is not None else 0
            rows.append(
                {
                    "chunk_id": m.chunk_id,
                    "entity_id": m.entity_id,
                    "sent_id": m.sent_id,
                    "start": off + m.start,
                    "end": off + m.end,
                    "text": m.text,
                    "type": m.type,
                    "method": m.method,
                    "lang": m.lang,
                    "confidence": round(m.confidence, 4),
                    "link_method": m.link_method,
                    "ambiguous": m.ambiguous,
                }
            )
    return rows


def triple_row(t: Triple) -> dict[str, Any]:
    return {
        "head": t.head,
        "tail": t.tail,
        "type": t.type,
        "negated": t.negated,
        "hedged": t.hedged,
        "status": t.status,
        "method": t.method,
        "confidence": round(t.confidence, 4),
        "evidence_count": t.evidence_count,
        "chunk_ids": t.chunk_ids,
        "doc_ids": t.doc_ids,
        "langs": t.langs,
        "pattern_id": t.pattern_id,
        "provenance_json": json.dumps(
            [p.model_dump() for p in t.provenance], ensure_ascii=False, separators=(",", ":")
        ),
    }


def triple_rows(g: KnowledgeGraph, include_unverified: bool = False) -> list[dict[str, Any]]:
    return [triple_row(t) for t in g.facts(include_unverified)]
