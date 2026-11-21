# Groq setup

1. Create a key at <https://console.groq.com> (API Keys).
2. Put it in `.env` at the project root (never commit `.env`; it is git-ignored):

    ```bash
    cp .env.example .env
    # edit .env:
    GROQ_API_KEY=gsk_...
    ```

3. Install the extra and check which models your key can use:

    ```bash
    pip install "leankg[groq]"
    leankg llm-models          # marks the configured model
    ```

4. Model IDs and prices live in `leankg.toml` (checked 2026-11; Groq retires models often):

    ```toml
    [llm]
    provider = "none"                # use --llm groq per run, or set "groq" here
    model = "openai/gpt-oss-20b"     # $0.075 / $0.30 per 1M tokens (in / out)
    escalation_model = ""            # e.g. "openai/gpt-oss-120b"
    reasoning_effort = "low"
    include_reasoning = false
    budget_calls = 500
    budget_tokens = 400000
    batch_size = 20
    max_concurrency = 2
    ```

    Every key can be overridden by env: `LEANKG_LLM_MODEL`, `LEANKG_LLM_BUDGET_CALLS`, …

5. Run: `leankg build data/ --domain manufacturing --llm groq`.

## Behaviour
- Structured Outputs with `strict: true`; every answer is still validated locally.
- The configured model is checked once against `models.list()`; a retired model fails
  with a clear message pointing to `leankg llm-models`.
- HTTP 429: waits for `retry-after` / `x-ratelimit-reset-*`, otherwise exponential
  backoff with jitter. The free tier is tight (for gpt-oss-20b roughly 30 requests and 8K
  tokens per minute), so keep `max_concurrency` at 1–2 and `batch_size` modest.
- Local alternative: `--llm ollama` with any local model that supports JSON-schema
  output (`[ollama]` extra, `llm.ollama_host`).
