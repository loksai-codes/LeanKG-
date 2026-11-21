"""JSON exporter: one file with documents, chunks, entities, mentions and triples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from leankg.export.rows import chunk_rows, document_rows, entity_rows, mention_rows, triple_rows
from leankg.graph import KnowledgeGraph


def graph_to_dict(g: KnowledgeGraph, include_unverified: bool = False) -> dict[str, Any]:
    return {
        "domain": g.domain,
        "metadata": g.metadata,
        "documents": document_rows(g),
        "chunks": chunk_rows(g, with_embedding=False),
        "entities": entity_rows(g),
        "mentions": mention_rows(g),
        "triples": triple_rows(g, include_unverified),
    }


def export_json(g: KnowledgeGraph, path: str | Path, include_unverified: bool = False) -> Path:
    out = Path(path)
    if out.suffix != ".json":
        out = out / "graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(graph_to_dict(g, include_unverified), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out
