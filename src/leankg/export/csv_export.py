"""CSV exporter: one file per node/relationship kind (Neo4j admin-import friendly)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from leankg.export.rows import chunk_rows, document_rows, entity_rows, mention_rows, triple_rows
from leankg.graph import KnowledgeGraph


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    for r in rows:
        for k in r:
            if k not in fields:
                fields.append(k)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(
                {k: "|".join(map(str, v)) if isinstance(v, list) else v for k, v in r.items()}
            )


def export_csv(
    g: KnowledgeGraph, folder: str | Path, include_unverified: bool = False
) -> list[Path]:
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    files = {
        "documents.csv": document_rows(g),
        "chunks.csv": chunk_rows(g, with_embedding=False),
        "entities.csv": entity_rows(g),
        "mentions.csv": mention_rows(g),
        "triples.csv": triple_rows(g, include_unverified),
    }
    paths = []
    for name, rows in files.items():
        _write(out / name, rows)
        paths.append(out / name)
    return paths
