# Benchmark results

The authoritative table lives in the project README and is regenerated from
`leankg eval` reports (`reports/<date>_<domain>_<setup>.json`). Setups are defined in
[Evaluation](EVAL.md).

Status 2026-11-21:

- **Seed fixtures** (18 hand-written sentences per language per pack): rules-only relation
  F1 — health EN 1.00, health JA 0.93, manufacturing EN 0.72, manufacturing JA 0.78;
  entity F1 0.96–1.00 (optimistic: same authors as the dictionaries).
- **Hard-case rate with the LLM off** (what setup C would send): health EN 5.6%, JA 11.1%;
  manufacturing EN 16.7%, JA 11.1%.
- **MaintIE** (EN, 1,076 texts, mapped types): entity F1 0.29 (P 0.78 / R 0.18), relation
  F1 0.00 with rules only.
- **NCBI Disease** (EN, 400 test sentences, Condition only): 0.00 with rules only — the
  stress dictionary has no genetic-disease vocabulary.
- **Setups C and D**: pending a Groq API key.
