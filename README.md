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

Status 2026-11-21. **Read the caveats.** Seed fixtures = 18 hand-written sentences per
language per pack (`domains/<pack>/eval/fixtures/`), written by the same people who wrote
the dictionaries, so entity scores on them are optimistic; independently labelled
Japanese gold sets (~100 sentences per pack) are pending. Setup B currently = rules +
spaCy/GiNZA NER (GLiNER and embeddings not yet installed in the benchmark environment).
C and D need a Groq key and are not run yet.

| Domain | Lang | Setup | Gold | Entity F1 | Relation F1 | LLM call rate | Cost / 1k docs |
|---|---|---|---|---|---|---|---|
| health_stress | en | A rules | seed (18) | 1.00 | 1.00 | 0% | $0 |
| health_stress | en | B rules+models | seed (18) | 1.00 | 1.00 | 0% | $0 |
| health_stress | ja | A rules | seed (18) | 0.99 | 0.93 | 0% | $0 |
| health_stress | ja | B rules+models | seed (18) | 0.99 | 0.93 | 0% | $0 |
| manufacturing | en | A rules | seed (18) | 1.00 | 0.72 | 0% | $0 |
| manufacturing | en | B rules+models | seed (18) | 1.00 | 0.72 | 0% | $0 |
| manufacturing | ja | A rules | seed (18) | 0.96 | 0.78 | 0% | $0 |
| manufacturing | ja | B rules+models | seed (18) | 0.96 | 0.78 | 0% | $0 |
| health_stress | en | A rules | NCBI Disease test, 400 sents (Condition only) | 0.00 | – | 0% | $0 |
| any | en/ja | C leankg (Groq fallback) | | pending key | | | |
| any | en/ja | D Groq only | | pending key | | | |

Reproduce: `uv run leankg eval --domain <pack> --setup A --fixtures` (see `docs/EVAL.md`).

## Development

```bash
uv sync                 # core + dev tools
uv sync --all-extras    # everything (GiNZA, scispaCy, GLiNER, embeddings, Neo4j, Groq)
uv run pytest -q
docker compose up -d    # Neo4j 5 + APOC for integration tests
```

## Licence

Apache-2.0. See `LICENSE`.
