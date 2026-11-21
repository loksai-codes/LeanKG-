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
- **Setups C and D** (Groq `openai/gpt-oss-20b`, seed fixtures), relation F1 · LLM call
  rate · cost per 1k docs:
  manufacturing EN C 0.81 · 16.7% · $0.013, D 0.89 · 94.4% · $0.052;
  manufacturing JA C 0.81 · 11.1% · $0.012, D 0.88 · 94.4% · $0.066;
  health EN C 0.94 · 5.6% · $0.008, D 0.88 · 94.4% · $0.037;
  health JA C 0.88 · 11.1% · $0.010, D 0.84 · 88.9% · $0.037.
- **Cache:** a second identical build made 0 LLM requests (cache hit rate 100%, $0).
