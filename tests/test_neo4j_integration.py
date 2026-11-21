"""Integration tests against a running Neo4j (docker compose up -d).

Skipped cleanly when the driver isn't installed or the server isn't reachable.
Connection: NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD (default password matches
docker-compose.yml's local default).
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

from leankg.config import parse_dotenv
from leankg.export.neo4j_writer import Neo4jWriter
from leankg.pipeline import Pipeline

from .conftest import ROOT

pytestmark = pytest.mark.integration


def _settings() -> tuple[str, str, str]:
    env = {**parse_dotenv(ROOT / ".env"), **os.environ}
    return (
        env.get("NEO4J_URI", "bolt://localhost:7687"),
        env.get("NEO4J_USER", "neo4j"),
        env.get("NEO4J_PASSWORD") or "leankg-dev-pw",
    )


@pytest.fixture(scope="module")
def writer() -> Iterator[Neo4jWriter]:
    neo4j = pytest.importorskip("neo4j")
    uri, user, password = _settings()
    try:
        driver = neo4j.GraphDatabase.driver(uri, auth=(user, password))
        driver.verify_connectivity()
    except Exception as exc:
        pytest.skip(f"Neo4j not reachable at {uri}: {exc}")
    w = Neo4jWriter(uri, user, password, driver=driver)
    w.clear()
    yield w
    w.close()


def test_build_examples_into_neo4j(writer: Neo4jWriter) -> None:
    pipe = Pipeline.from_domain("health_stress", llm="none")
    pipe.build(ROOT / "examples" / "health_stress")
    counts = writer.write_graph(pipe.graph)
    assert counts["documents"] == 3
    rows = writer.run(
        "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e:Entity) "
        "RETURN count(DISTINCT d) AS docs, count(DISTINCT c) AS chunks, "
        "count(DISTINCT e) AS ents, collect(DISTINCT c.lang) AS langs"
    )
    r = rows[0]
    assert r["docs"] == 3
    assert r["ents"] > 10
    assert set(r["langs"]) == {"en", "ja"}
    labels = writer.run("MATCH (e:Entity:Stressor {id: 'HS:stress'}) RETURN e.name_ja AS ja")
    assert labels[0]["ja"] == "ストレス"


def test_cjk_fulltext_index_finds_japanese(writer: Neo4jWriter) -> None:
    writer.run("CALL db.awaitIndexes(60)")
    hits = writer.search_entities("ストレス")
    assert any(h["id"] == "HS:stress" for h in hits)
    hits = writer.search_entities("不眠")
    assert any(h["id"] == "HS:insomnia" for h in hits)


def test_rewrite_is_idempotent(writer: Neo4jWriter) -> None:
    before = writer.run("MATCH (n) RETURN count(n) AS n")[0]["n"]
    pipe = Pipeline.from_domain("health_stress", llm="none")
    pipe.build(ROOT / "examples" / "health_stress")
    writer.write_graph(pipe.graph)
    after = writer.run("MATCH (n) RETURN count(n) AS n")[0]["n"]
    assert before == after
