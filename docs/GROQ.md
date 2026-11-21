# Groq LLM fallback — design

Replaces the Anthropic adapter from the original plan. Interface is unchanged:

```python
class LLMClient(Protocol):
    def classify(self, batch: list[HardCase]) -> list[LLMVerdict]: ...
```

Adapters: `GroqClient` (default hosted), `OllamaClient` (local), `NoneClient` (LLM off),
`FakeClient` (tests — returns canned verdicts from a fixture file).

## Model choice (checked Nov 2026 — re-check before you build)
Groq's model list changes often. `llama-3.1-8b-instant` and `llama-3.3-70b-versatile`
were announced deprecated (shutdown Aug 16, 2026) even though they may still appear on
the models page, so **don't use them**.

| Role | Model ID | Price per 1M tokens (in / out) | Strict JSON schema |
|---|---|---|---|
| Default referee | `openai/gpt-oss-20b` | $0.075 / $0.30 | yes |
| Escalation (optional) | `openai/gpt-oss-120b` | $0.15 / $0.60 | yes |

Both are production models. Put IDs and prices in config:

```toml
# leankg.toml
[llm]
provider = "groq"
model = "openai/gpt-oss-20b"
escalation_model = ""            # e.g. "openai/gpt-oss-120b"; empty = off
price_in_per_mtok = 0.075
price_out_per_mtok = 0.30
budget_calls = 500
budget_tokens = 400000
batch_size = 20                  # hard cases per request
temperature = 0
```

On startup, `GroqClient` calls `client.models.list()` once and fails with a clear error if
the configured model isn't served any more (suggesting `leankg llm-models` to list them).

## Request shape
- Groq is OpenAI-compatible. Use the official `groq` Python SDK, `chat.completions.create`.
- Use **Structured Outputs** with `response_format={"type": "json_schema", "json_schema":
  {"name": "verdicts", "strict": true, "schema": ...}}`.
- Strict-mode schema rules: **every property listed in `required`**, **every object has
  `additionalProperties: false`**, optional fields are expressed as nullable unions
  (`["string", "null"]`). Generate the schema from Pydantic and post-process it to meet
  these rules (write a unit test that asserts this for the generated schema).
- Streaming and tool use can't be combined with Structured Outputs — don't use them.
- Still validate every answer locally with Pydantic, and reject verdicts that reference an
  entity index or relation type not in the request (strict decoding isn't a substitute
  for checking).
- gpt-oss models are reasoning models: check the current docs for the reasoning-effort
  parameter and use the lowest setting that keeps F1 — it cuts output tokens and cost.

## Prompt (language-neutral)
The LLM never sees raw documents. Per hard case it gets: the sentence (EN or JA), the
entities already found as a numbered list `[i] surface (Type)`, and the allowed relation
types for those type pairs. It answers with **indices and relation names only**, never
free text. That makes the answer identical in shape for Japanese and English input.

```json
{"verdicts": [
  {"case_id": "c17", "relations": [
     {"head": 0, "tail": 2, "type": "CAUSED_BY", "negated": false, "hedged": false,
      "confidence": 0.82}
  ],
  "link_choice": null}
]}
```

System prompt is English. Few-shot examples come from the pack's `llm_hints.md` plus
`llm_hints.ja.md` when the batch contains Japanese sentences. Batches are grouped by
language so the right examples are attached.

## Cost and rate limits
- SQLite cache key: `sha256(normalized_sentence + entity_list + schema_version + model + prompt_version)`.
- Near-duplicate dedupe: normalize (NFKC, whitespace, digits → `0`) then MinHash or
  RapidFuzz ratio ≥ 95 inside a run.
- Budget cap: when calls or tokens hit the limit, the remaining hard cases are kept as
  `method="cooc"`, `status="unverified"` — never an exception.
- Handle HTTP 429 with the `retry-after` header + exponential backoff with jitter; the
  free tier has tight per-minute limits, so default `max_concurrency = 2`.
- Cost = actual `usage.prompt_tokens` / `completion_tokens` from responses × config prices.
