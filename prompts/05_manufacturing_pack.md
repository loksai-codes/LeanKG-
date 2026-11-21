# M5 — Manufacturing pack, EN + JA, no engine changes (paste into Claude Code)

Rule for this milestone: **no changes under `src/leankg/`** unless you stop and explain
why the engine can't express something, and I agree. Everything goes in
`domains/manufacturing/`.

1. Ontology per docs/PLAN.md manufacturing schema with `labels.ja` for every type and
   relation; TPS concepts (Jidoka 自働化, Andon アンドン, Poka-yoke ポカヨケ, 5 Whys なぜなぜ分析,
   Kaizen 改善, Just-in-Time ジャスト・イン・タイム) as dictionary entries.
2. Optional: import IOF maintenance ontology with `leankg import-owl` (keep `@ja` labels if
   any) — report what was usable.
3. Data download scripts (never commit data): NHTSA complaints/recalls, MaintIE, Japanese
   Wikipedia TPS articles. Check and note each source's licence/terms in
   `domains/manufacturing/DATA.md`. Ask me before using any Japanese government data
   source whose terms are unclear.
4. EN + JA dependency patterns and triggers for PART_OF, HAS_FAILURE_MODE, CAUSED_BY,
   DETECTED_BY, FIXED_BY, OCCURS_AT, PREVENTS. JA few-shot examples in `llm_hints.ja.md`.
5. Gold: MaintIE converter (EN) + Label Studio set for ~100 JA sentences.
6. Demo query file `domains/manufacturing/demo_queries.cypher`: walk CAUSED_BY chains
   (graph なぜなぜ分析), "seen this defect before?" via vector index, maintenance actions with
   evidence — with a Japanese-input example that finds entities via the CJK full-text index.

Done when: A/B/C/D table for manufacturing per language, and `git diff --stat src/` is
empty for this milestone. Update PLAN.md.
