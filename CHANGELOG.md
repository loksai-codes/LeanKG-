# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### M0 — scaffold
- Project skeleton (uv, src layout, hatchling), extras `med`, `ja`, `gliner`, `embed`,
  `neo4j`, `groq`, `ollama`, `dev`; dev tools in a dependency group.
- Core Pydantic models (`Document`, `Chunk`, `Sentence`, `Mention`, `Entity`, `Triple`,
  `Provenance`, `HardCase`, `LLMVerdict`, `RunReport` with `llm_call_rate`,
  `cache_hit_rate`, `est_cost_usd`, `by_lang`).
- `Stage` protocol (`process(doc) -> doc`) and `Pipeline` with no-op placeholder stages.
- Config loading from `leankg.toml`, `.env` and `LEANKG_*` env overrides.
- Kana/CJK-ratio language detection.
- Tooling: ruff, mypy (strict), pytest, pre-commit, GitHub Actions CI, docker-compose
  Neo4j 5 + APOC, Apache-2.0 licence, Typer CLI stubs.
