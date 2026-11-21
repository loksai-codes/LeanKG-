# M1 — Ingest, preprocessing, dictionary/regex entities, Neo4j (paste into Claude Code)

Re-read CLAUDE.md and docs/JAPANESE.md sections 1–4 and 8. Plan first, then build test-first.

1. **Ingest stage**: loaders for PDF, HTML, CSV (configurable text column), TXT. Clean
   whitespace, keep metadata. Detect language per document and per chunk. Chunker that is
   sentence-aware (target ~800 chars EN / ~400 chars JA — make it config).
2. **LanguageProfile**: `EnglishProfile` (en_core_web_sm) and `JapaneseProfile` (ja_ginza),
   lazy-loaded and cached. Japanese sentence splitting must handle 。！？ and newlines.
   `normalize()` per docs/JAPANESE.md §3, with tests for full-width, half-width kana,
   hiragana/katakana and long-vowel variants.
3. **DomainPack loader**: Pydantic models for ontology.yaml (with `labels: {en, ja}`),
   dictionaries CSV (`id,type,lang,term,synonyms,source`), patterns/entities.jsonl (with
   `lang`), models.yaml. Clear validation errors with file + line.
4. **Dictionary entity stage**: EN via PhraseMatcher (attr LOWER) / EntityRuler; JA via
   character-level Aho-Corasick on normalized text with an offset map back to the original
   text and `char_span(alignment_mode="expand")`. Longest match wins; overlapping matches
   resolved deterministically. Tests with JA terms that Sudachi splits.
5. **Regex entity stage**: per-language patterns; JA tests with full-width digits.
6. **Writers**: JSON/CSV/NetworkX exporters, and `neo4j_writer` with constraints, batched
   `UNWIND … MERGE` (1,000 rows), Document/Chunk/Entity/MENTIONS, double labels
   (`:Entity:<Type>`), `name_ja`/aliases arrays, `lang` on Chunk, and a full-text index
   with the `cjk` analyzer. Integration test against docker-compose Neo4j (marked).
7. Seed tiny packs: health_stress (≈30 EN terms + ≈20 JA terms, e.g. ストレス, 不眠, 睡眠障害,
   うつ病, 運動, 瞑想) and manufacturing (≈30 EN + ≈30 JA, e.g. 油圧ポンプ, 摩耗, 漏れ,
   ベアリング, ポカヨケ, アンドン). Mark seed data clearly as hand-written examples.
8. `leankg build --domain X PATH --llm none --out json|neo4j` works end to end and prints a
   RunReport (per-language counts).

Done when: tests pass offline; a small EN + JA sample folder builds into Neo4j with
Document, Chunk and Entity nodes and the JA full-text index returns hits. Update PLAN.md.
