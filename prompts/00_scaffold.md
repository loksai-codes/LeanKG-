# M0 — Scaffold (paste into Claude Code)

Read CLAUDE.md, docs/PLAN.md, docs/GROQ.md and docs/JAPANESE.md fully before doing anything.
Then enter plan mode and show me your plan for this milestone before writing code.

Goal: an empty-but-real project skeleton that installs, lints, type-checks and passes tests.

Do:
1. `pyproject.toml` using uv, Python >=3.11, package `leankg` under `src/`. Core deps:
   pydantic>=2, pyyaml, typer, rapidfuzz, spacy>=3.7,<3.9 (confirm what GiNZA and scispaCy
   currently accept and tell me if they conflict). Extras: `med`, `ja`, `gliner`, `embed`,
   `neo4j`, `groq`, `ollama`, `dev`. Use dependency groups for dev tools.
2. Layout:
   `src/leankg/{__init__,cli,config,models,pipeline,report}.py`,
   `src/leankg/stages/{ingest,preprocess,entities,linking,relations,validate,route,write}/`,
   `src/leankg/lang/{base,detect,en,ja}.py`,
   `src/leankg/llm/{base,groq_client,ollama_client,none_client,fake_client,cache,prompt}.py`,
   `src/leankg/domain/{pack,loader,owl_import}.py`,
   `src/leankg/export/{json_export,csv_export,nx_export,neo4j_writer}.py`,
   `domains/health_stress/`, `domains/manufacturing/` (folder skeletons per PLAN.md),
   `tests/`, `notebooks/`, `docs/`.
3. Core data models in `models.py` (Pydantic): `Document`, `Chunk`, `Sentence` (with
   `lang`), `Mention`, `Entity`, `Triple`, `Provenance`, `HardCase`, `LLMVerdict`,
   `RunReport` (with `llm_call_rate`, `cache_hit_rate`, `est_cost_usd`, `by_lang`).
4. `Stage` protocol (`process(doc) -> doc`) and a `Pipeline` that runs a configured list of
   stages; stages not yet built are no-op placeholders with a TODO and a test.
5. `config.py` loading `leankg.toml` + env overrides (`LEANKG_*`, `GROQ_API_KEY`).
6. `lang/detect.py` with the kana/CJK-ratio heuristic + tests (EN, JA, mixed).
7. Tooling: ruff (lint+format), mypy (strict on `src/`), pytest, pre-commit,
   `.github/workflows/ci.yml` (lint, mypy, tests, core install only), `docker-compose.yml`
   for Neo4j 5 with APOC, `.env.example`, `.gitignore`, Apache-2.0 LICENSE, README with goal,
   architecture list and an empty benchmark table (columns per language).
8. `leankg --help` works via Typer with stub commands: build, eval, review-llm, llm-models,
   import-owl.

Done when: `uv sync`, ruff, mypy and pytest all pass; CI file is valid; I can run
`uv run leankg --help`. Update the M0 checkbox in docs/PLAN.md.
