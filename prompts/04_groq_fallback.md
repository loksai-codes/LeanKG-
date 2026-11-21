# M4 — Groq LLM fallback (paste into Claude Code)

Read docs/GROQ.md fully. Check the current Groq docs (models page, structured outputs,
rate limits) before coding and tell me if anything in docs/GROQ.md is out of date.
Plan first.

1. **Router stage**: build `HardCase`s using exactly the rules in docs/PLAN.md. Everything
   else goes straight through. Record why each case was routed (`reason` enum).
2. **Prompt builder** (`llm/prompt.py`): language-neutral, numbered entities, allowed
   relations per type pair, few-shot from `llm_hints.md` / `llm_hints.ja.md`, versioned
   (`PROMPT_VERSION`). Snapshot tests for EN and JA prompts.
3. **GroqClient**: official `groq` SDK, Structured Outputs `strict: true` with a schema
   generated from Pydantic and post-processed (all fields required, nullable unions,
   `additionalProperties: false`) + a test that walks the schema to assert it. Local
   Pydantic validation and index/type checks on every verdict. Model availability check on
   startup. 429 handling with retry-after + backoff + jitter, `max_concurrency` config.
   Optional escalation model for verdicts below a confidence floor.
4. **Cache** (SQLite) with the key from docs/GROQ.md; **dedupe** of near-identical
   sentences within a run; **batching** grouped by language; **budget cap** that degrades
   to unverified candidates.
5. **OllamaClient** (same interface, JSON format mode) and **FakeClient** for tests.
6. **RunReport**: llm_call_rate, cache_hit_rate, tokens in/out, est_cost_usd — overall and
   per language. Print it at the end of every `build`.
7. **`leankg review-llm`**: groups logged LLM verdicts by (relation, trigger-ish n-grams /
   JA bunsetsu head) and suggests dictionary / trigger entries; `--apply` writes them into
   the pack after confirmation.
8. Eval setups C (full) and D (Groq on every sentence — with a hard budget so it can't
   surprise me with cost).

Done when: setups C and D are in the README table per language with the LLM call rate and
cost per 1,000 docs, and a second `build` run on the same data shows ~100% cache hits.
Update PLAN.md.
