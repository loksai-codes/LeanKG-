"""Neo4j writer: constraints, indexes and batched ``UNWIND … MERGE`` writes.

Graph model::

    (:Document)-[:HAS_CHUNK]->(:Chunk {lang, embedding})-[:MENTIONS {start,end,method}]->
    (:Entity:<Type> {name, name_ja, aliases_en, aliases_ja})-[:<REL> {...}]->(:Entity)

Labels and relationship types can't be query parameters, so they're validated against
an identifier regex before being put in the Cypher text.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any

from leankg.export.rows import chunk_rows, document_rows, entity_rows, mention_rows, triple_rows
from leankg.graph import KnowledgeGraph

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

SCHEMA_STATEMENTS: tuple[str, ...] = (
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE INDEX chunk_lang IF NOT EXISTS FOR (c:Chunk) ON (c.lang)",
    "CREATE INDEX entity_type IF NOT EXISTS FOR (e:Entity) ON (e.type)",
    # CJK analyzer so Japanese names and text are searchable (bigram tokenization).
    "CREATE FULLTEXT INDEX entity_names IF NOT EXISTS FOR (e:Entity) "
    "ON EACH [e.name, e.name_ja, e.aliases_text] "
    "OPTIONS {indexConfig: {`fulltext.analyzer`: 'cjk'}}",
    "CREATE FULLTEXT INDEX chunk_text IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text] "
    "OPTIONS {indexConfig: {`fulltext.analyzer`: 'cjk'}}",
)


def safe_ident(name: str) -> str:
    if not _IDENT.match(name):
        raise ValueError(f"unsafe label/relationship name: {name!r}")
    return name


def batched(rows: list[dict[str, Any]], size: int) -> Iterator[list[dict[str, Any]]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def vector_index_statement(dimensions: int, name: str = "chunk_embedding") -> str:
    return (
        f"CREATE VECTOR INDEX {safe_ident(name)} IF NOT EXISTS FOR (c:Chunk) ON (c.embedding) "
        f"OPTIONS {{indexConfig: {{`vector.dimensions`: {int(dimensions)}, "
        "`vector.similarity_function`: 'cosine'}}"
    )


class Neo4jWriter:
    """Writes a :class:`KnowledgeGraph` to Neo4j 5 (needs the ``[neo4j]`` extra)."""

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
        database: str = "neo4j",
        batch_size: int = 1000,
        driver: Any = None,
    ) -> None:
        if driver is None:
            try:
                from neo4j import GraphDatabase
            except ImportError as exc:  # pragma: no cover - depends on extras
                raise ImportError("Neo4j output needs: pip install 'leankg[neo4j]'") from exc
            driver = GraphDatabase.driver(uri, auth=(user, password))
        self.driver = driver
        self.database = database
        self.batch_size = batch_size
        self.statements: list[str] = []  # executed Cypher, kept for tests/debugging

    def close(self) -> None:
        self.driver.close()

    def __enter__(self) -> Neo4jWriter:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    # ---------------------------------------------------------------- helpers
    def run(self, query: str, **params: Any) -> list[Any]:
        self.statements.append(query)
        records, _summary, _keys = self.driver.execute_query(
            query, parameters_=params, database_=self.database
        )
        return list(records)

    def _unwind(self, query: str, rows: list[dict[str, Any]]) -> int:
        n = 0
        for batch in batched(rows, self.batch_size):
            self.run(query, rows=batch)
            n += len(batch)
        return n

    # ----------------------------------------------------------------- schema
    def setup_schema(self, embedding_dim: int | None = None) -> None:
        for stmt in SCHEMA_STATEMENTS:
            self.run(stmt)
        if embedding_dim:
            self.run(vector_index_statement(embedding_dim))

    def clear(self) -> None:
        """Delete every node (used by integration tests on a throwaway database)."""
        self.run("MATCH (n) DETACH DELETE n")

    # ------------------------------------------------------------------ write
    def write_documents(self, rows: list[dict[str, Any]]) -> int:
        return self._unwind(
            "UNWIND $rows AS r MERGE (d:Document {id: r.id}) "
            "SET d.title = r.title, d.source = r.source, d.url = r.url, d.date = r.date, "
            "d.lang = r.lang, d.domain = r.domain",
            rows,
        )

    def write_chunks(self, rows: list[dict[str, Any]]) -> int:
        return self._unwind(
            "UNWIND $rows AS r MATCH (d:Document {id: r.doc_id}) "
            "MERGE (c:Chunk {id: r.id}) "
            "SET c.text = r.text, c.lang = r.lang, c.index = r.index, c.start = r.start, "
            "c.end = r.end, c.embedding = r.embedding "
            "MERGE (d)-[:HAS_CHUNK]->(c)",
            rows,
        )

    def write_entities(self, rows: list[dict[str, Any]]) -> int:
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            by_type[safe_ident(r["type"])].append(r)
        n = 0
        for type_name, typed in sorted(by_type.items()):
            n += self._unwind(
                f"UNWIND $rows AS r MERGE (e:Entity {{id: r.id}}) SET e:`{type_name}`, "
                "e.type = r.type, e.name = r.name, e.name_ja = r.name_ja, "
                "e.aliases_en = r.aliases_en, e.aliases_ja = r.aliases_ja, "
                "e.aliases_text = r.aliases_text, e.ontology_id = r.ontology_id, "
                "e.domain = r.domain, e.lang_seen = r.lang_seen, "
                "e.mention_count = r.mention_count, e.confidence = r.confidence",
                typed,
            )
        return n

    def write_mentions(self, rows: list[dict[str, Any]]) -> int:
        return self._unwind(
            "UNWIND $rows AS r MATCH (c:Chunk {id: r.chunk_id}) MATCH (e:Entity {id: r.entity_id}) "
            "MERGE (c)-[m:MENTIONS {start: r.start, end: r.end}]->(e) "
            "SET m.method = r.method, m.lang = r.lang, m.confidence = r.confidence, "
            "m.text = r.text, m.sent_id = r.sent_id, m.link_method = r.link_method, "
            "m.ambiguous = r.ambiguous",
            rows,
        )

    def write_triples(self, rows: Iterable[dict[str, Any]]) -> int:
        by_type: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            by_type[safe_ident(r["type"])].append(r)
        n = 0
        for rel, typed in sorted(by_type.items()):
            n += self._unwind(
                "UNWIND $rows AS r MATCH (h:Entity {id: r.head}) MATCH (t:Entity {id: r.tail}) "
                f"MERGE (h)-[x:`{rel}` {{negated: r.negated}}]->(t) "
                "SET x.confidence = r.confidence, x.method = r.method, x.status = r.status, "
                "x.hedged = r.hedged, x.evidence_count = r.evidence_count, "
                "x.chunk_ids = r.chunk_ids, x.doc_ids = r.doc_ids, x.langs = r.langs, "
                "x.pattern_id = r.pattern_id, x.provenance_json = r.provenance_json",
                typed,
            )
        return n

    def write_metadata(self, domain: str, metadata: dict[str, str]) -> None:
        self.run(
            "MERGE (m:LeanKGMeta {domain: $domain}) SET m += $props",
            domain=domain,
            props=metadata,
        )

    def write_graph(self, g: KnowledgeGraph, include_unverified: bool = False) -> dict[str, int]:
        """Write everything; idempotent (re-running updates instead of duplicating)."""
        chunks = chunk_rows(g)
        dim = next((len(c["embedding"]) for c in chunks if c.get("embedding")), None)
        self.setup_schema(embedding_dim=dim)
        counts = {
            "documents": self.write_documents(document_rows(g)),
            "chunks": self.write_chunks(chunks),
            "entities": self.write_entities(entity_rows(g)),
            "mentions": self.write_mentions(mention_rows(g)),
            "triples": self.write_triples(triple_rows(g, include_unverified)),
        }
        if g.metadata:
            self.write_metadata(g.domain, g.metadata)
        return counts

    # ----------------------------------------------------------------- search
    def search_entities(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text search on entity names/aliases (CJK analyzer)."""
        records = self.run(
            "CALL db.index.fulltext.queryNodes('entity_names', $q) YIELD node, score "
            "RETURN node.id AS id, node.name AS name, node.name_ja AS name_ja, score "
            "ORDER BY score DESC LIMIT $limit",
            q=query,
            limit=limit,
        )
        return [dict(r) for r in records]
