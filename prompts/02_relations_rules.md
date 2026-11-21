# M2 — Relations by rules, negation/hedging, validation (paste into Claude Code)

Re-read docs/PLAN.md (pipeline 5–6) and docs/JAPANESE.md §6–7. Plan first.

1. **Dependency-pattern stage** using spaCy DependencyMatcher, patterns loaded from
   `patterns/relations.<lang>.yaml` (pack data, not code). EN: active/passive "X causes Y",
   "Y is caused by X", "X reduces Y". JA: が/を + verb, により/によって + 発生, 〜に起因する,
   〜が原因で, 〜を軽減する. Inspect GiNZA's actual parse of each example sentence first and
   write the patterns from what it really produces — put those parse dumps in test fixtures.
2. **Trigger-lexicon stage**: per relation, per language trigger words with a window rule
   (EN tokens; JA bunsetsu). Lower confidence than dependency hits.
3. **Typed co-occurrence**: candidate pairs only if the schema allows the type pair; for JA
   restrict to pairs whose bunsetsu are connected in the parse. Low confidence.
4. **Negation/hedging**: EN via negspaCy (in `[med]` extra; fall back to a simple rule set
   if not installed); JA via the rules in docs/JAPANESE.md §7. Output `negated`, `hedged`,
   `complex`. Negated triples are stored as negative evidence, not as facts.
5. **Validate & score**: drop/flag schema violations; confidence = method prior × pattern
   weight × negation/hedge penalty, all from config. Merge duplicate triples, increment
   `evidence_count`, keep `chunk_ids` and `langs`.
6. Provenance on every edge; Neo4j writer writes typed relationships with properties.
7. ≥ 15 EN and ≥ 15 JA relation test sentences per pack, including negated and hedged ones
   (e.g. 運動はストレスを軽減しなかった, 摩耗が漏れの原因である可能性がある).

Done when: health pack produces triples for both languages browsable in Neo4j Bloom, and
the rule-only relation tests pass. Update PLAN.md.
