# leankg — design and build plan (Groq + Japanese edition)

Condensed from the original "KG Builder Library: Design and Build Plan" (Nov 21, 2026),
with two changes: the hosted LLM is **Groq** (`docs/GROQ.md`) and **Japanese** is supported
from the start (`docs/JAPANESE.md`).

## Goals
- LLM call rate < 10% of sentences, reported every run; fully offline with `llm="none"`.
- One engine, swappable **domain packs** (health_stress, manufacturing).
- One engine, swappable **language profiles** (en, ja).
- Full provenance + confidence on every node/edge.
- Neo4j output ready for GraphRAG (lexical layer + domain layer, vector index).
- Portfolio quality: tests, docs, benchmark table, demo notebooks.

Non-goals v1: no chatbot/GraphRAG answering, no large-model training, no web UI.

## Pipeline (each stage: `process(doc) -> doc`)
1. **Ingest** — PDF (pypdf/pdfplumber), HTML (trafilatura), CSV (pandas), text. Keep
   metadata. Detect language per doc/chunk. Chunk + sentence split.
2. **Preprocess** — spaCy via the chunk's LanguageProfile (EN: en_core_web_sm [+ scispaCy
   abbreviation expansion]; JA: GiNZA).
3. **Entities, cheapest first** — dictionary (EN PhraseMatcher/EntityRuler; JA char-level
   Aho-Corasick) → regex → statistical NER → GLiNER (multilingual).
4. **Linking** — exact/synonym → RapidFuzz → multilingual embeddings; merge duplicates;
   flag ambiguous links (top-2 within margin).
5. **Relations** — dependency patterns (per language) → trigger lexicon (per language) →
   typed co-occurrence → negation/hedging (negspaCy for EN, rules for JA).
6. **Validate & score** — schema check (allowed source/target types), confidence score.
7. **Route** — high confidence → graph; hard cases → LLM fallback (Groq) or kept flagged.
8. **Write** — Neo4j (UNWIND…MERGE, batches of ~1,000, constraints, vector index,
   CJK full-text index) or JSON/CSV/NetworkX export.

### Hard-case rules (when a sentence goes to the LLM)
≥ 2 typed entities but no rule relation · ambiguous link · triple confidence < 0.6 ·
negation/hedging marked `complex`. Never: sentences with no entities or a high-confidence
rule hit.

### Keeping calls low
Confidence gate · constrained JSON question (indices only) · SQLite cache · near-duplicate
dedupe · batching · budget cap (degrade, never fail) · `leankg review-llm` to promote
recurring LLM answers into dictionary/trigger entries.

## Domain pack layout
```
domains/<pack>/
  ontology.yaml            # entity + relation types, allowed from/to, labels {en, ja}
  dictionaries/*.csv       # id,type,lang,term,synonyms(|-separated),source
  patterns/entities.jsonl  # regex/token patterns, each with "lang"
  patterns/relations.en.yaml
  patterns/relations.ja.yaml
  models.yaml              # per-language model names (spaCy, GLiNER, embeddings)
  llm_hints.md             # 3–5 EN worked examples
  llm_hints.ja.md          # 3–5 JA worked examples
  eval/gold.en.jsonl
  eval/gold.ja.jsonl
  eval/fixtures/           # tiny CI sets
```

ontology.yaml example:
```yaml
version: 1
entities:
  Component:   {labels: {en: Component, ja: 部品}}
  FailureMode: {labels: {en: Failure mode, ja: 故障モード}}
  Cause:       {labels: {en: Cause, ja: 原因}}
relations:
  HAS_FAILURE_MODE: {from: [Component], to: [FailureMode], labels: {ja: 故障モードを持つ}}
  CAUSED_BY:        {from: [FailureMode], to: [Cause],      labels: {ja: 原因}}
```
Packs load via a Pydantic-validated `DomainPack`, can ship as separate pip packages via
entry points, and an rdflib importer converts OWL/RDF/TTL (keeping `rdfs:label@ja`).

Starting schemas (keep small: 6–8 entity types, 5–7 relations):
- **health_stress** — Condition, Symptom, Stressor, Intervention, Biomarker, Instrument,
  Outcome · HAS_SYMPTOM, INCREASES_RISK_OF, REDUCES, TREATS, MEASURED_BY, ASSOCIATED_WITH.
- **manufacturing** — Machine, Component, FailureMode, Cause, Observation,
  MaintenanceAction, Process/Station, Sensor, Countermeasure, TPSConcept · PART_OF,
  HAS_FAILURE_MODE, CAUSED_BY, DETECTED_BY, FIXED_BY, OCCURS_AT, PREVENTS.

## Graph model
```
(:Document {id,title,source,url,date,lang})-[:HAS_CHUNK]->
(:Chunk {id,text,lang,embedding})-[:MENTIONS {start,end,method}]->
(:Entity:<Type> {id,name,name_ja,aliases_en,aliases_ja,ontology_id,domain})
(:Entity)-[:<REL> {confidence,method,evidence_count,chunk_ids,langs}]->(:Entity)
```
Repeated evidence increments `evidence_count`. Constraints on `Entity.id`, `Chunk.id`.

## Evaluation
Setups: A rules only · B rules+models · C full leankg (Groq fallback) · D Groq-only baseline.
Metrics per setup **and per language**: entity P/R/F1 (exact + partial), linking accuracy,
relation P/R/F1, LLM call rate, est. cost per 1,000 docs, docs/min on laptop CPU.
Gold: BC5CDR / NCBI Disease (EN health), MaintIE (EN maintenance), ~100 hand-labelled
sentences per pack per language.

## Milestones (~14 weeks at 10–12 h/week; JA adds ~2 weeks)
- [x] **M0 (week 1)** Repo scaffold, tooling, CI, docker-compose Neo4j, core models.
- [x] **M1 (weeks 2–3)** Ingest, language detection, preprocessing (EN + JA), dictionary
      + regex entities, Neo4j writer + exporters. *Done:* 50 MedlinePlus pages + 20 JA
      pages in Neo4j as Document/Chunk/Entity.
- [x] **M2 (weeks 4–5)** Rule relations EN + JA, negation/hedging, schema validation,
      provenance. *Done:* browsable triples in Neo4j Bloom for both languages.
- [x] **M3 (weeks 6–7)** NER, GLiNER multilingual, fuzzy + multilingual embedding linking,
      confidence scores, eval harness. *Done:* first gold sets, setups A and B reported.
- [ ] **M4 (weeks 8–9)** Groq fallback: router, constrained prompts, cache, dedupe, batching,
      budget cap, `review-llm`. *Done:* setups C and D + LLM call rate reported.
- [ ] **M5 (weeks 10–12)** Manufacturing pack (NHTSA, MaintIE, JA TPS/recall text) with no
      engine code changes. *Done:* JA question demo data in graph.
- [ ] **M6 (weeks 13–14)** Docs site, two notebooks (one JA), README benchmark, v0.1.0 to PyPI.

## Public API target
```python
from leankg import Pipeline

pipe = Pipeline.from_domain("manufacturing", llm="groq", llm_budget=500)
report = pipe.build("./data/nhtsa", neo4j_uri="bolt://localhost:7687")
print(report.llm_call_rate, report.by_lang["ja"].f1)
```
