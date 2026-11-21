# LLM cost controls

The LLM is a referee for hard cases, not the extractor. Every build prints:

- **hard%** — sentences the router flagged as hard (whether or not an LLM answered);
- **llm%** (`llm_call_rate`) — sentences handed to the LLM layer, cache hits included;
- **cache%** — of those, answered from the SQLite cache or in-run dedupe;
- **tok_in / tok_out / cost$** — real token counts × prices from `leankg.toml`.

## What keeps calls low

| Control | Where | Default |
|---|---|---|
| Confidence gate | sentences with a confident rule hit are never routed | `scoring.accept_threshold = 0.6` |
| Hard-case rules only | ≥2 relatable entities but no rule relation · ambiguous link · low-confidence rule triple · complex negation | — |
| Indices-only answers | the model returns entity indices + relation names, never free text | — |
| Strict JSON schema | no retries for malformed output | `strict: true` |
| SQLite cache | key = normalized sentence + entities + schema + model + prompt version | `.leankg/cache.sqlite` |
| Near-duplicate dedupe | same entities, RapidFuzz ratio ≥ 95 → one call | `llm.dedupe_threshold = 95` |
| Batching by language | `batch_size` cases per request | 20 |
| Budget cap | after `budget_calls` requests or `budget_tokens` tokens, remaining cases stay `unverified` — never an error | 500 / 400,000 |
| Reasoning effort | gpt-oss `reasoning_effort` | `low` |
| Learn from answers | `leankg review-llm --apply` turns repeats into trigger rules | — |

A second build over the same data costs nothing: everything comes from the cache
(`cache% = 100`).

## Estimating before you spend
Run with `--llm none` first: `hard%` tells you how many sentences *would* go to the LLM.
Setup D (`leankg eval --setup D --llm groq --llm-budget 50`) shows what an LLM-only
approach would cost on the same data — always give it a budget.
