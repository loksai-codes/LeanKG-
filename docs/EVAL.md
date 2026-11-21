# Evaluation

## Setups

| Setup | What runs | LLM |
|---|---|---|
| **A** rules only | dictionary, regex, exact/synonym + RapidFuzz linking, dependency patterns, triggers, co-occurrence, negation | off |
| **B** rules + models | A + statistical NER (spaCy / GiNZA / optional scispaCy) + GLiNER + embedding linking + chunk embeddings | off |
| **C** full leankg | B + LLM fallback for hard cases only | Groq (default) |
| **D** LLM-only relations | same entity stages as B; *no* relation rules; every sentence with ≥ 2 entities goes to the LLM | Groq, hard budget |

Run: `uv run leankg eval --domain health_stress --setup A --lang all`.
The command prints a markdown table and writes `reports/<date>_<domain>_<setup>.json`.

## Metrics
- **Entities** — exact (same span and type) and partial (overlapping span, same type)
  precision / recall / F1.
- **Linking accuracy** — over gold entities that carry a concept `id` and have an
  exactly matching predicted mention: share whose predicted `ontology_id` equals it.
- **Relations** — a predicted fact (status `accepted` or `negative`) matches a gold
  relation when both argument spans overlap the gold arguments in the same direction
  (either direction for `ASSOCIATED_WITH`), the relation type is the same and the
  `negated` flag agrees. Candidates that were never confirmed don't count.
- **LLM call rate** — sentences handed to the LLM layer / all sentences (cache hits
  included). **Hard-case rate** — sentences the router flagged. **Cost** — real token
  counts × the prices in `leankg.toml`; *cost per 1,000 docs* = cost / docs × 1000.
- **Throughput** — docs/min and sentences/s on the machine running the eval.

## Gold format (JSONL)
One example per line; see `src/leankg/eval/gold.py` for the full spec.

```json
{"id": "hs-ja-007", "lang": "ja", "text": "運動は血圧を下げなかった。",
 "entities": [{"text": "運動", "type": "Intervention", "id": "HS:exercise"},
              {"start": 3, "end": 5, "type": "Biomarker", "id": "HS:blood_pressure"}],
 "relations": [{"head": 0, "tail": 1, "type": "REDUCES", "negated": true}],
 "source": "seed"}
```

Entity offsets may be given explicitly or resolved from `text` (first occurrence after the
previous entity, or `"occurrence": n`). Relation `head`/`tail` index into `entities`.

## Where gold data lives
- `domains/<pack>/eval/fixtures/gold.<lang>.jsonl` — **18 hand-written seed sentences**
  per language per pack (authored by the leankg developers *before* running the
  pipeline on them and different from the relation unit-test sentences). They keep CI and
  the eval command runnable. Because the same people wrote the dictionaries, these
  scores are optimistic — especially entity F1.
- `domains/<pack>/eval/gold.<lang>.jsonl` — the real gold sets (e.g. ~100 independently
  labelled Japanese sentences per pack). `leankg eval` prefers these when present.
- Public corpora are converted by scripts and kept under `data/` (never committed):
  - `scripts/download_ncbi_disease.py` → `data/ncbi_disease/gold.en.jsonl`
  - `scripts/download_bc5cdr.py` → `data/bc5cdr/gold.en.jsonl`
  - evaluate with `--gold <file> --types Condition` (entity-only; relation columns show –).

## Labelling Japanese gold data in Label Studio
1. `uv run leankg labelstudio config --domain manufacturing --lang ja > config.xml` and
   paste it into a new Label Studio project (Settings → Labeling Interface → Code). The
   config uses `granularity="symbol"` so spans can start inside Japanese words.
2. Put one sentence per line in `sentences.ja.txt`, then
   `uv run leankg labelstudio tasks sentences.ja.txt --domain manufacturing --lang ja --out tasks.json --preannotate`
   and import `tasks.json`. `--preannotate` shows leankg's guesses as predictions —
   correct them; don't accept them blindly (that would bias the benchmark).
3. Label each entity span with its type. For relations, draw from **head to tail** (the
   arrow direction matters: `漏れ → 摩耗` for CAUSED_BY), pick the relation label and add
   the `negated` label when the sentence denies the relation (〜ではなかった).
4. Export as JSON and convert:
   `uv run leankg labelstudio convert export.json --lang ja --domain manufacturing --out domains/manufacturing/eval/gold.ja.jsonl`

## CI regression check
`.github/workflows/ci.yml` runs setup B (LLM off, GLiNER/embeddings skipped) on the
fixtures and fails if entity or relation F1 drops more than 2 points below
`tests/fixtures/eval_baseline.json`. Regenerate the baseline with
`scripts/update_baseline.sh` when a drop is intended.
