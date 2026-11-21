# leankg starter kit for Claude Code

## Setup (once)
1. Create an empty GitHub repo `leankg` and clone it.
2. Copy into the repo root: `CLAUDE.md`, `docs/`, `prompts/`, `.env.example`.
3. Install uv, Docker (for Neo4j), and Claude Code. Get a Groq API key from console.groq.com.
4. `cp .env.example .env` and fill in `GROQ_API_KEY` (you won't need it until M4).
5. Commit: `git add . && git commit -m "Add design docs and Claude Code kit"`.

## Build loop (per milestone)
1. Run `claude` in the repo.
2. Paste the contents of the milestone prompt, e.g. `prompts/00_scaffold.md`.
3. Review the plan Claude proposes, then let it build. Push back on anything that breaks
   the non-negotiables in CLAUDE.md.
4. When it says done, run the checks yourself:
   `uv run ruff check . && uv run mypy src && uv run pytest -q`
5. Commit, push, close the milestone's GitHub issue. Start a fresh Claude Code session (`/clear`)
   for the next milestone so context stays clean — CLAUDE.md and docs/ carry the memory.

## Order
00_scaffold → 01_ingest_entities_neo4j → 02_relations_rules → 03_models_linking_eval →
04_groq_fallback → 05_manufacturing_pack → 06_polish_publish

## Tips
- Big milestones: ask Claude Code to split them ("do steps 1–3 only, then stop").
- Japanese patterns: always have it print GiNZA's parse of a sentence before writing a
  dependency pattern for it. Guessing the parse is the most common source of bugs.
- Labelling the ~100 Japanese gold sentences is your job, and it's what makes the
  benchmark believable.
