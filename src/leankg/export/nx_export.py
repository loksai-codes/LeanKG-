"""NetworkX exporter (and GraphML file output)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from leankg.export.rows import chunk_rows, document_rows, entity_rows, mention_rows, triple_rows
from leankg.graph import KnowledgeGraph


def _flat(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if v is None:
            continue
        out[k] = "|".join(map(str, v)) if isinstance(v, list) else v
    return out


def to_networkx(g: KnowledgeGraph, include_unverified: bool = False) -> Any:
    """A ``networkx.MultiDiGraph`` with Document, Chunk and Entity nodes."""
    import networkx as nx

    graph = nx.MultiDiGraph(domain=g.domain)
    for d in document_rows(g):
        graph.add_node(d["id"], label="Document", **_flat(d))
    for c in chunk_rows(g, with_embedding=False):
        graph.add_node(c["id"], label="Chunk", **_flat(c))
        graph.add_edge(c["doc_id"], c["id"], key="HAS_CHUNK", type="HAS_CHUNK")
    for e in entity_rows(g):
        graph.add_node(e["id"], label="Entity", **_flat(e))
    for m in mention_rows(g):
        attrs = _flat(m)
        attrs["entity_type"] = attrs.pop("type")
        graph.add_edge(m["chunk_id"], m["entity_id"], type="MENTIONS", **attrs)
    for t in triple_rows(g, include_unverified):
        graph.add_edge(t["head"], t["tail"], key=t["type"], **_flat(t))
    return graph


def export_graphml(g: KnowledgeGraph, path: str | Path, include_unverified: bool = False) -> Path:
    import networkx as nx

    out = Path(path)
    if out.suffix != ".graphml":
        out = out / "graph.graphml"
    out.parent.mkdir(parents=True, exist_ok=True)
    nx.write_graphml(to_networkx(g, include_unverified), out)
    return out
