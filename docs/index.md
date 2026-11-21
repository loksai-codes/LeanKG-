# leankg

**Turn English and Japanese documents into a Neo4j knowledge graph.** Classic NLP —
dictionaries, regexes, dependency patterns, a trigger lexicon, spaCy/GiNZA — does most of
the work. An LLM (Groq by default) only sees the *hard cases* the rules can't settle, and
every run tells you how many sentences that was and what it cost.

## Install

```bash
pip install "leankg[ja,neo4j]"          # Japanese + Neo4j output
pip install "leankg[ja,neo4j,groq]"     # + Groq LLM fallback
pip install "leankg[med]"               # scispaCy + negspaCy (English medical)
pip install "leankg[gliner,embed]"      # GLiNER + multilingual embeddings (pulls torch)
python -m spacy download en_core_web_sm
```

The core install runs fully offline with `--llm none`.

## 30-second quick start

```bash
leankg build examples/health_stress --domain health_stress --llm none --out json
```

```text
leankg run — domain=health_stress llm=none
lang  docs  sents  mentions  entities  triples  neg  hard%  llm%  cache%  tok_in  tok_out   cost$
  en     2     12        35        25       18    1    ...
  ja     1     11        24        17       11    1    ...
```

In Python:

```python
from leankg import Pipeline

pipe = Pipeline.from_domain("manufacturing", llm="none")
report = pipe.build("examples/manufacturing", out="json", out_path="out/")
print(report.llm_call_rate, report.by_lang["ja"].triples)
```

Write to Neo4j (`docker compose up -d` starts Neo4j 5 + APOC; set `NEO4J_PASSWORD` in `.env`):

```bash
leankg build examples/manufacturing --domain manufacturing --out neo4j --csv-text-column summary
```

Then try `domains/manufacturing/demo_queries.cypher` — including a Japanese full-text
lookup and a graph なぜなぜ分析 over `CAUSED_BY` chains.

## Commands

| Command | What it does |
|---|---|
| `leankg build PATH --domain X` | ingest → entities → relations → graph; prints the RunReport |
| `leankg eval --domain X --setup A\|B\|C\|D` | benchmark against gold data (see [Evaluation](EVAL.md)) |
| `leankg review-llm --domain X [--apply]` | turn recurring LLM answers into trigger/dictionary rules |
| `leankg llm-models` | list models your Groq key can use |
| `leankg import-owl FILE` | OWL/RDF/TTL → pack `ontology.yaml` (keeps `@ja` labels) |
| `leankg labelstudio config\|tasks\|convert` | label gold data in Label Studio |

!!! note "Windows with Smart App Control"
    Smart App Control blocks unsigned native extensions (spaCy's compiled modules) in a
    Windows virtualenv. Use WSL (Ubuntu) for development on such machines; Linux and macOS
    are unaffected.
