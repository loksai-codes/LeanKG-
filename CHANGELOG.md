# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### M3 — statistical NER, GLiNER, linking, evaluation harness
- NER stage: spaCy/GiNZA NER plus optional extra spaCy pipelines (e.g. scispaCy), labels
  mapped to ontology types via `models.yaml`; missing models become RunReport warnings.
- GLiNER stage (`[gliner]`): multilingual checkpoint from `models.yaml`, per-language
  labels, only on sentences with fewer than N entities.
- Linking: embedding fallback (`[embed]`, one multilingual sentence-transformers model,
  disk-cached concept embeddings); chunk-embedding stage + Neo4j vector index; model name
  recorded in graph metadata.
- Evaluation harness `leankg eval --setup A|B|C|D --lang en|ja|all`: documented gold JSONL
  format, entity P/R/F1 (exact + partial), linking accuracy, relation P/R/F1, LLM call
  rate, cost per 1k docs, throughput; markdown table + `reports/<date>_<domain>_<setup>.json`;
  `--types` filter for entity-only corpora; baseline check with tolerance.
- 18 hand-written seed gold sentences per language per pack (`eval/fixtures/`), CI job
  running setup B against `tests/fixtures/eval_baseline.json` (fails on > 2 pt drop).
- Download + conversion scripts for NCBI Disease and BC5CDR (PubTator); data never
  committed.
- Label Studio support: config generator (character-level spans for Japanese), task
  files with optional pre-annotation, export → gold converter (`leankg labelstudio …`).

### M2 — relations by rules, negation/hedging, validation
- Dependency-pattern stage (spaCy `DependencyMatcher`, patterns are pack data in
  `patterns/relations.<lang>.yaml`), with conjunct expansion and a subtree fallback
  ("the risk of X" → X). EN and JA patterns written from real en_core_web_sm / GiNZA
  parses (dumps in `tests/fixtures/parses/`).
- Trigger-lexicon stage with `between` / `after` / `any` positions, windows in profile
  units (tokens EN, bunsetsu JA) and type-aware rule choice.
- Typed co-occurrence candidates (schema-allowed pairs only; JA restricted to
  bunsetsu-connected pairs).
- Negation/hedging: EN rules plus negspaCy termsets when `[med]` is installed; JA rules
  (ない/なかった/ません…, かもしれない/可能性…, complex cases like ないとは言えない).
- Validate & score stage: schema check with reverse/flip handling, confidence from
  config priors/penalties, negated triples kept as negative evidence, duplicate merging
  with `evidence_count`, provenance on every edge; typed Neo4j relationships.
- 40 EN + 36 JA relation test sentences across both packs; pack loader rejects YAML
  booleans in patterns (`on` → True).

### M1 — ingest, preprocessing, dictionary/regex entities, Neo4j
- Loaders for TXT/MD, HTML (trafilatura), PDF (pypdf), CSV (configurable text/id
  column) and JSONL; UTF-8/CP932/EUC-JP decoding; whitespace cleaning.
- Language detection per document and per paragraph; sentence-aware chunker with
  per-language targets (800 EN / 400 JA chars) that never mixes languages in a chunk.
- `EnglishProfile` (en_core_web_sm, blank fallback, rule sentence splitter, plural
  variants) and `JapaneseProfile` (GiNZA, dependency-free script-run tokenizer fallback,
  。！？/newline splitter, NFKC → katakana → long-vowel folding normalization with an
  offset map back to the original text).
- Domain pack loader with Pydantic validation and `file:line` error messages
  (ontology.yaml, dictionaries/*.csv, patterns/entities.jsonl, models.yaml).
- Dictionary entity stage: EN PhraseMatcher (LOWER), JA character-level Aho-Corasick,
  longest match wins. Regex entity stage on NFKC text (full-width digits match).
- Linking: dictionary id / exact synonym / RapidFuzz (WRatio EN, ratio JA) with
  ambiguity flags; cross-language mentions merge into one entity.
- Corpus graph merge; JSON, CSV, NetworkX/GraphML exporters; Neo4j writer with
  constraints, batched `UNWIND … MERGE`, `:Entity:<Type>` labels, `name_ja`/alias
  arrays and CJK full-text indexes.
- Seed packs `health_stress` and `manufacturing` (hand-written EN + JA dictionaries) and
  hand-written sample documents in `examples/`.
- `leankg build` works end to end and prints a per-language RunReport.

### M0 — scaffold
- Project skeleton (uv, src layout, hatchling), extras `med`, `ja`, `gliner`, `embed`,
  `neo4j`, `groq`, `ollama`, `dev`; dev tools in a dependency group.
- Core Pydantic models (`Document`, `Chunk`, `Sentence`, `Mention`, `Entity`, `Triple`,
  `Provenance`, `HardCase`, `LLMVerdict`, `RunReport` with `llm_call_rate`,
  `cache_hit_rate`, `est_cost_usd`, `by_lang`).
- `Stage` protocol (`process(doc) -> doc`) and `Pipeline` with no-op placeholder stages.
- Config loading from `leankg.toml`, `.env` and `LEANKG_*` env overrides.
- Kana/CJK-ratio language detection.
- Tooling: ruff, mypy (strict), pytest, pre-commit, GitHub Actions CI, docker-compose
  Neo4j 5 + APOC, Apache-2.0 licence, Typer CLI stubs.
