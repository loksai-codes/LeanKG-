# leankg

**Turn English and Japanese documents into a Neo4j knowledge graph — classic NLP does most
of the work, an LLM (Groq) is called only for the hard cases the rules can't settle.**

- Low LLM use: target < 10% of sentences sent to the LLM; every run reports
  `llm_call_rate`, `cache_hit_rate` and `est_cost_usd`. Runs fully offline with `--llm none`.
- One engine, swappable **domain packs** (`health_stress`, `manufacturing`) and
  **language profiles** (`en`, `ja`).
- Provenance (doc, chunk, sentence offsets, method, language, confidence) on every node
  and edge.

> Status: under active development (pre-0.1). See `docs/PLAN.md` for milestones.

## Architecture

Every stage is a class with `process(doc) -> doc`, testable alone and skippable by config:

1. **Ingest** — PDF / HTML / CSV / TXT, language detection per document and chunk,
   sentence-aware chunking.
2. **Preprocess** — spaCy via the chunk's `LanguageProfile` (EN `en_core_web_sm`,
   JA GiNZA).
3. **Entities** — dictionary → regex → statistical NER → GLiNER (cheapest first).
4. **Linking** — exact/synonym → RapidFuzz → multilingual embeddings.
5. **Relations** — dependency patterns → trigger lexicon → typed co-occurrence →
   negation/hedging.
6. **Validate & score** — schema check, confidence.
7. **Route** — confident triples go to the graph; hard cases go to the LLM (or stay flagged).
8. **Write** — Neo4j (`UNWIND … MERGE`, constraints, vector + CJK full-text indexes) or
   JSON / CSV / NetworkX.

## Benchmark

| Domain | Lang | Setup | Entity F1 | Relation F1 | LLM call rate | Cost / 1k docs |
|---|---|---|---|---|---|---|
| | en | A rules | | | | |
| | en | B rules+models | | | | |
| | en | C leankg (Groq fallback) | | | | |
| | en | D Groq only | | | | |
| | ja | A rules | | | | |
| | ja | B rules+models | | | | |
| | ja | C leankg (Groq fallback) | | | | |
| | ja | D Groq only | | | | |

## Development

```bash
uv sync                 # core + dev tools
uv sync --all-extras    # everything (GiNZA, scispaCy, GLiNER, embeddings, Neo4j, Groq)
uv run pytest -q
docker compose up -d    # Neo4j 5 + APOC for integration tests
```

## Licence

Apache-2.0. See `LICENSE`.
