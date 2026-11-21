import json
from pathlib import Path
from typing import Any

import pytest

from leankg.export import export_csv, export_graphml, export_json, to_networkx
from leankg.export.neo4j_writer import Neo4jWriter, safe_ident, vector_index_statement
from leankg.graph import KnowledgeGraph

from .helpers import ENTITY_STAGES, make_ctx
from .helpers import run_stages as _run


def _graph() -> KnowledgeGraph:
    g = KnowledgeGraph(domain="health_stress")
    for i, text in enumerate(["Stress causes insomnia.", "ストレスは不眠を引き起こす。"]):
        g.add_document(_run(text, ENTITY_STAGES, doc_id=f"d{i}"))
    return g


def test_graph_merges_entities_across_documents() -> None:
    g = _graph()
    stress = g.entities["HS:stress"]
    assert stress.lang_seen == ["en", "ja"]
    assert stress.mention_count == 2


def test_json_export(tmp_path: Path) -> None:
    path = export_json(_graph(), tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert {d["id"] for d in data["documents"]} == {"d0", "d1"}
    stress = next(e for e in data["entities"] if e["id"] == "HS:stress")
    assert stress["name_ja"] == "ストレス"
    assert "ストレス" in stress["aliases_ja"]
    assert all(m["chunk_id"] and m["entity_id"] for m in data["mentions"])


def test_csv_export(tmp_path: Path) -> None:
    paths = export_csv(_graph(), tmp_path)
    assert {p.name for p in paths} == {
        "documents.csv", "chunks.csv", "entities.csv", "mentions.csv", "triples.csv",
    }  # fmt: skip
    assert "ストレス" in (tmp_path / "entities.csv").read_text(encoding="utf-8")


def test_networkx_and_graphml(tmp_path: Path) -> None:
    g = to_networkx(_graph())
    assert g.nodes["HS:stress"]["label"] == "Entity"
    assert g.has_edge("d0", "d0:c0")
    out = export_graphml(_graph(), tmp_path)
    assert out.read_text(encoding="utf-8").startswith("<?xml")


# ------------------------------------------------------- neo4j (no server)
class FakeDriver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute_query(self, query: str, parameters_: dict[str, Any], database_: str) -> Any:
        self.calls.append((query, parameters_))
        return [], None, []

    def close(self) -> None:
        pass


def test_neo4j_writer_batches_and_labels() -> None:
    driver = FakeDriver()
    writer = Neo4jWriter("bolt://x", "u", "p", batch_size=1, driver=driver)
    counts = writer.write_graph(_graph())
    assert counts["documents"] == 2
    queries = [q for q, _ in driver.calls]
    assert any("FULLTEXT INDEX entity_names" in q and "'cjk'" in q for q in queries)
    assert any("CONSTRAINT entity_id" in q for q in queries)
    assert any("SET e:`Stressor`" in q for q in queries)
    unwinds = [p["rows"] for q, p in driver.calls if q.startswith("UNWIND")]
    assert all(len(rows) == 1 for rows in unwinds)  # batch_size respected


def test_safe_ident_rejects_injection() -> None:
    assert safe_ident("HAS_SYMPTOM") == "HAS_SYMPTOM"
    with pytest.raises(ValueError, match="unsafe"):
        safe_ident("X`]->(n) DETACH DELETE n //")


def test_vector_index_statement() -> None:
    stmt = vector_index_statement(384)
    assert "`vector.dimensions`: 384" in stmt


def test_pipeline_export_requires_password() -> None:
    from leankg.pipeline import Pipeline

    ctx = make_ctx()
    pipe = Pipeline(ctx=ctx, stage_names=["ingest"])
    with pytest.raises(RuntimeError, match="NEO4J_PASSWORD"):
        pipe.export("neo4j")
