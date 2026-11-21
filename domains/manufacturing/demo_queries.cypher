// leankg manufacturing pack — demo queries (Neo4j 5).
// Build first, e.g.:
//   uv run leankg build examples/manufacturing --domain manufacturing --out neo4j --csv-text-column summary
// Parameters can be set in Neo4j Browser with  :param q => 'ベアリング'

// 1. Japanese input → entities via the CJK full-text index (works with half/full-width).
//    :param q => '焼き付き'
CALL db.index.fulltext.queryNodes('entity_names', $q) YIELD node, score
RETURN node.id AS id, node.name AS name, node.name_ja AS name_ja, labels(node) AS labels, score
ORDER BY score DESC LIMIT 10;

// 2. Graph なぜなぜ分析 (5 Whys): walk CAUSED_BY chains back from a failure, up to 5 steps.
//    Only accepted, non-negated edges; shows the evidence count of each step.
//    :param q => '漏れ'
CALL db.index.fulltext.queryNodes('entity_names', $q) YIELD node AS start
WITH start LIMIT 1
MATCH path = (start)-[:CAUSED_BY*1..5]->(root:Entity)
WHERE all(r IN relationships(path) WHERE r.negated = false AND r.status = 'accepted')
RETURN [n IN nodes(path) | coalesce(n.name_ja, n.name)] AS why_chain,
       [r IN relationships(path) | r.evidence_count] AS evidence,
       length(path) AS depth
ORDER BY depth DESC LIMIT 10;

// 3. Which components fail how, and what fixed it (with evidence and languages seen).
MATCH (c:Component)-[h:HAS_FAILURE_MODE]->(f:FailureMode)
OPTIONAL MATCH (f)-[x:FIXED_BY]->(a:MaintenanceAction)
RETURN c.name AS component, c.name_ja AS 部品, f.name AS failure, f.name_ja AS 故障,
       collect(DISTINCT a.name) AS fixes, h.evidence_count AS evidence, h.langs AS langs
ORDER BY evidence DESC LIMIT 25;

// 4. Maintenance actions with their source sentences (provenance back to chunks).
MATCH (f:Entity)-[x:FIXED_BY]->(a:MaintenanceAction)
UNWIND x.chunk_ids AS cid
MATCH (ch:Chunk {id: cid})
RETURN f.name AS problem, a.name AS action, x.method AS method, x.confidence AS confidence,
       ch.lang AS lang, left(ch.text, 160) AS evidence
ORDER BY confidence DESC LIMIT 25;

// 5. "Have we seen this defect before?" — vector search over chunk embeddings.
//    Needs chunk embeddings ([embed] extra) so the `chunk_embedding` vector index exists.
//    Use the embedding of a chunk you already have (here: the first chunk mentioning 異音),
//    or pass your own query vector as $vec (same model, 'query: ' prefix for e5 models).
MATCH (seed:Chunk)-[:MENTIONS]->(:Entity {id: 'MF:noise'})
WITH seed LIMIT 1
CALL db.index.vector.queryNodes('chunk_embedding', 5, seed.embedding) YIELD node, score
WHERE node <> seed
RETURN node.lang AS lang, score, left(node.text, 160) AS similar_report;

// 6. Negative evidence: causes that were explicitly ruled out (〜ではなかった / "was not caused by").
MATCH (f:Entity)-[r:CAUSED_BY {negated: true}]->(c:Entity)
RETURN coalesce(f.name_ja, f.name) AS failure, coalesce(c.name_ja, c.name) AS ruled_out_cause,
       r.evidence_count AS times, r.langs AS langs;

// 7. TPS concepts and what they prevent.
MATCH (t:TPSConcept)-[p:PREVENTS]->(x)
RETURN t.name AS concept, t.name_ja AS 概念, collect(coalesce(x.name_ja, x.name)) AS prevents;
