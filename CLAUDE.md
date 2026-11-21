# leankg — project rules for Claude Code

leankg is an open-source Python library that turns documents (English **and Japanese**)
into a Neo4j knowledge graph. Classic NLP does most of the work; an LLM (Groq) is called
only for the hard cases the rules can't settle. Full design: `docs/PLAN.md`.
Japanese design: `docs/JAPANESE.md`. Groq adapter design: `docs/GROQ.md`.

## Non-negotiables
1. **Low LLM use.** Target < 10% of sentences sent to the LLM. Every run reports
   `llm_call_rate`, `cache_hit_rate` and `est_cost_usd`. The pipeline must run fully
   offline with `llm="none"`.
2. **Domain-agnostic engine.** Code under `src/leankg/` never mentions a domain term
   ("stress", "gearbox", "ストレス"). Everything domain-specific lives in `domains/<pack>/`.
3. **Language-agnostic engine.** Code under `src/leankg/` never branches on `if lang == "ja"`
   outside `src/leankg/lang/`. Language behaviour goes through a `LanguageProfile`
   (see `docs/JAPANESE.md`). Adding a language = adding a profile + pack files.
4. **Provenance on everything.** Every node and edge records doc id, chunk id, sentence
   offsets, `method` (`dict|regex|ner|gliner|dep|trigger|cooc|llm`), `lang` and `confidence`.
5. **Same stage interface.** Every pipeline stage is a class with `process(doc) -> doc`.
   Stages are testable alone and can be skipped by config.

## Stack (do not swap without asking)
Python 3.11+, uv, pyproject.toml · spaCy 3 · scispaCy (EN medical) · negspaCy (EN) ·
GiNZA `ja_ginza` (JA, SudachiPy) · GLiNER multilingual · RapidFuzz · sentence-transformers
(multilingual model) · rdflib · Pydantic v2 + PyYAML · `groq` SDK + Ollama adapter ·
SQLite cache · neo4j driver (Neo4j 5) · Typer · pytest, ruff, mypy, pre-commit, GitHub Actions.

Heavy / conflicting deps go in extras: `leankg[med]` (scispaCy, negspaCy),
`leankg[ja]` (ginza, ja_ginza, jaconv), `leankg[gliner]`, `leankg[neo4j]`, `leankg[groq]`.
The core install must import and run tests without any of them.

## Working rules
- Test first where practical. Every stage gets unit tests with tiny EN **and** JA fixtures.
- Never call a real LLM or a real Neo4j in unit tests. Use the `none`/fake LLM client and
  the JSON/NetworkX exporter. Integration tests are marked `@pytest.mark.integration`.
- Never hardcode a Groq model ID or price in code; they live in config (`leankg.toml` /
  env). Groq retires models often — see `docs/GROQ.md`.
- Secrets only from env (`GROQ_API_KEY`, `NEO4J_PASSWORD`). Never commit `.env`.
- Before finishing a task: `uv run ruff check . && uv run ruff format --check . &&
  uv run mypy src && uv run pytest -q`. All must pass.
- Keep modules small (one stage per module). Public API is re-exported in `leankg/__init__.py`.
- When a milestone is done, update the checklist in `docs/PLAN.md` and the README benchmark
  table, and write a short entry in `CHANGELOG.md`.
- If a dependency version conflict appears (spaCy pins of GiNZA vs scispaCy are the likely
  one), stop and report the options instead of silently downgrading.

## Commands
- `uv sync --all-extras` — install everything
- `uv run pytest -q` — unit tests (offline)
- `uv run pytest -m integration` — needs Neo4j (`docker compose up -d`) and/or `GROQ_API_KEY`
- `uv run leankg build --domain health_stress ./data/sample --llm none`
- `uv run leankg review-llm --domain health_stress` — show LLM answers worth promoting to rules
- `uv run leankg eval --domain manufacturing --setup A|B|C|D --lang ja`
