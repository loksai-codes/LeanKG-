# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
