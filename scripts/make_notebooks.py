"""Generate the demo notebooks (plain nbformat-4 JSON, no outputs) and optionally run them.

uv run python scripts/make_notebooks.py          # write notebooks/*.ipynb
uv run python scripts/make_notebooks.py --run    # also execute every code cell (smoke test)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NB_DIR = ROOT / "notebooks"

SETUP = """from pathlib import Path
import os

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
os.chdir(ROOT)  # so leankg finds domains/ and leankg.toml
from leankg import Pipeline
from leankg.report import render_report"""

NEO4J = """# Connect to Neo4j if it's running (docker compose up -d); otherwise use NetworkX.
from leankg.config import load_config

cfg = load_config()
writer = None
try:
    from leankg.export.neo4j_writer import Neo4jWriter
    pw = cfg.neo4j.password.get_secret_value() if cfg.neo4j.password else "leankg-dev-pw"
    writer = Neo4jWriter(cfg.neo4j.uri, cfg.neo4j.user, pw)
    writer.driver.verify_connectivity()
    writer.clear()  # demo database only!
    print(writer.write_graph(pipe.graph))
    writer.run("CALL db.awaitIndexes(60)")
except Exception as exc:  # no server / no [neo4j] extra
    writer = None
    print(f"Neo4j not available ({type(exc).__name__}); falling back to NetworkX")

from leankg.export import to_networkx
G = to_networkx(pipe.graph)

def cypher(query, **params):
    if writer is None:
        return None
    return [dict(r) for r in writer.run(query, **params)]"""


def md(text: str) -> dict[str, object]:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": text.strip().splitlines(keepends=True),
    }


def code(text: str) -> dict[str, object]:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip().splitlines(keepends=True)}  # fmt: skip


def notebook(cells: list[dict[str, object]]) -> dict[str, object]:
    return {
        "cells": cells,
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                     "language_info": {"name": "python"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }  # fmt: skip


HEALTH = notebook([
    md("""
# leankg — health_stress (English) demo

Builds a small knowledge graph from the hand-written sample documents with the LLM
**off** (`llm="none"`), so it runs without any API key. Then it runs three Cypher queries
(one in Japanese) if Neo4j is up, or the NetworkX equivalents otherwise.
"""),
    code(SETUP),
    code('''pipe = Pipeline.from_domain("health_stress", llm="none")
report = pipe.build(ROOT / "examples" / "health_stress", out="json", out_path="out/health_stress")
print(render_report(report))'''),
    md("## Facts extracted by rules (accepted and negative evidence)"),
    code('''ents = pipe.graph.entities
for t in sorted(pipe.graph.facts(), key=lambda t: -t.confidence):
    neg = "NOT " if t.negated else ""
    print(f"{ents[t.head].name:28} {neg}{t.type:18} {ents[t.tail].name:28} "
          f"{t.method:8} conf={t.confidence:.2f} langs={t.langs}")'''),
    md("## Three queries (Neo4j, or NetworkX fallback)"),
    code(NEO4J),
    code('''# 1. What increases the risk of insomnia?
rows = cypher("MATCH (s)-[r:INCREASES_RISK_OF {negated: false}]->(c {id: 'HS:insomnia'}) "
              "RETURN s.name AS cause, r.evidence_count AS evidence")
if rows is None:
    rows = [{"cause": G.nodes[u]["name"], "evidence": d["evidence_count"]}
            for u, v, k, d in G.edges(keys=True, data=True)
            if v == "HS:insomnia" and k == "INCREASES_RISK_OF" and d.get("negated") is False]
rows'''),
    code('''# 2. Negative evidence: interventions that did NOT reduce something
rows = cypher("MATCH (i:Intervention)-[r:REDUCES {negated: true}]->(x) RETURN i.name AS intervention, x.name AS target")
if rows is None:
    rows = [{"intervention": G.nodes[u]["name"], "target": G.nodes[v]["name"]}
            for u, v, k, d in G.edges(keys=True, data=True) if k == "REDUCES" and d.get("negated") is True]
rows'''),
    code('''# 3. Japanese input: full-text search with the CJK analyzer
rows = cypher("CALL db.index.fulltext.queryNodes('entity_names', $q) YIELD node, score "
              "RETURN node.id AS id, node.name AS name, node.name_ja AS name_ja, score", q="ストレス")
if rows is None:
    rows = [{"id": n, "name": d.get("name"), "name_ja": d.get("name_ja")}
            for n, d in G.nodes(data=True) if "ストレス" in str(d.get("aliases_text", "")) + str(d.get("name_ja", ""))]
rows'''),
])  # fmt: skip

MANUFACTURING = notebook([
    md("""
# leankg — manufacturing (日本語) demo

日本語の保全記録（手書きサンプル）から知識グラフを作ります。LLM は **オフ**（`llm="none"`）なので
API キーは不要です。最後に日本語の Cypher クエリを 3 つ実行します（Neo4j がなければ NetworkX で代替）。
"""),
    code(SETUP),
    code('''pipe = Pipeline.from_domain("manufacturing", llm="none")
report = pipe.build(ROOT / "examples" / "manufacturing" / "maintenance_log_ja.txt",
                    out="json", out_path="out/manufacturing_ja")
print(render_report(report))'''),
    md("## 抽出された関係（ルールのみ）"),
    code('''ents = pipe.graph.entities
for t in pipe.graph.facts():
    h, tl = ents[t.head], ents[t.tail]
    neg = "（否定）" if t.negated else ""
    print(f"{h.name_ja or h.name} -[{t.type}{neg}]-> {tl.name_ja or tl.name}  ({t.method}, {t.confidence:.2f})")'''),
    md("## クエリ 3 つ"),
    code(NEO4J),
    code('''# 1. 全文検索（CJK アナライザ）: 「焼き付き」
rows = cypher("CALL db.index.fulltext.queryNodes('entity_names', $q) YIELD node, score "
              "RETURN node.id AS id, node.name_ja AS name_ja, score", q="焼き付き")
if rows is None:
    rows = [{"id": n, "name_ja": d.get("name_ja")} for n, d in G.nodes(data=True)
            if "焼き付き" in str(d.get("name_ja", "")) + str(d.get("aliases_text", ""))]
rows'''),
    code('''# 2. グラフで「なぜなぜ分析」: CAUSED_BY を最大 5 段たどる
rows = cypher("MATCH p=(f:FailureMode)-[:CAUSED_BY*1..5]->(c) "
              "WHERE all(r IN relationships(p) WHERE r.negated = false) "
              "RETURN [n IN nodes(p) | coalesce(n.name_ja, n.name)] AS chain")
if rows is None:
    rows = [{"chain": [G.nodes[u].get("name_ja"), G.nodes[v].get("name_ja")]}
            for u, v, k, d in G.edges(keys=True, data=True) if k == "CAUSED_BY" and d.get("negated") is False]
rows'''),
    code('''# 3. TPS 概念と防止対象
rows = cypher("MATCH (t:TPSConcept)-[:PREVENTS]->(x) RETURN t.name_ja AS 概念, collect(coalesce(x.name_ja, x.name)) AS 防止")
if rows is None:
    rows = [{"概念": G.nodes[u].get("name_ja"), "防止": G.nodes[v].get("name_ja")}
            for u, v, k, d in G.edges(keys=True, data=True) if k == "PREVENTS"]
rows'''),
])  # fmt: skip


def run(path: Path) -> None:
    nb = json.loads(path.read_text(encoding="utf-8"))
    env: dict[str, object] = {}
    cwd = Path.cwd()
    os.chdir(NB_DIR)
    try:
        for i, cell in enumerate(nb["cells"]):
            if cell["cell_type"] == "code":
                src = "".join(cell["source"])
                lines = src.strip().splitlines()
                last = lines[-1] if lines else ""
                exec(compile(src, f"{path.name}[{i}]", "exec"), env)
                if last == "rows":
                    print(repr(eval(last, env))[:400])
    finally:
        os.chdir(cwd)
    print(f"OK {path.name}")


def main() -> None:
    NB_DIR.mkdir(exist_ok=True)
    for name, nb in [("health_stress_en.ipynb", HEALTH), ("manufacturing_ja.ipynb", MANUFACTURING)]:
        (NB_DIR / name).write_text(
            json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"wrote notebooks/{name}")
    if "--run" in sys.argv:
        for name in ("health_stress_en.ipynb", "manufacturing_ja.ipynb"):
            run(NB_DIR / name)


if __name__ == "__main__":
    main()
