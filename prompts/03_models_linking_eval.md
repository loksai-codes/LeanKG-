# M3 — Statistical NER, GLiNER, linking, evaluation harness (paste into Claude Code)

Re-read docs/JAPANESE.md §4–5 and §9. Plan first.

1. **Statistical NER stage**: EN general spaCy NER + scispaCy models for med packs (extra
   `[med]`); JA GiNZA NER. Map model labels to ontology types via `models.yaml`.
2. **GLiNER stage** (extra `[gliner]`): multilingual checkpoint from models.yaml; labels per
   language from the pack; threshold in config; run only on sentences where cheaper stages
   found < 2 entities (configurable) to save CPU. Batch sentences.
3. **Linking stage**: exact/synonym → RapidFuzz (`fuzz.ratio` on normalized chars for JA,
   `WRatio` for EN) → multilingual embeddings (extra `[embed]`, model in config, ontology
   label embeddings cached to disk). Mark `ambiguous=True` when top-2 within margin. Merge
   duplicate entities across languages when they link to the same ontology id.
4. **Chunk embeddings** with the same multilingual model; Neo4j vector index.
5. **Eval harness** `leankg eval --domain X --setup A|B --lang en|ja|all`: gold JSONL format
   (document it), entity P/R/F1 exact + partial, linking accuracy, relation P/R/F1,
   throughput. Output a markdown table to stdout and `reports/<date>_<setup>.json`.
6. Loaders for BC5CDR / NCBI Disease (EN) converted to the gold format — download scripts
   only, never commit the datasets.
7. Add `eval/fixtures/` (10–20 sentences per language per pack) and a CI job that runs
   setup B with LLM off and fails if F1 drops > 2 points versus a committed baseline file.

Done when: setups A and B are reported for both languages on the first gold sets.
I'll hand-label the ~100 JA sentences myself; give me a Label Studio config and a
converter to the gold format. Update PLAN.md and README table.
