# leankg — build progress

> If a session ends or context is cleared: read this file first, then CLAUDE.md, then the
> prompt for the current milestone in `prompts/`. Continue from "Next".

## Current milestone
M1 — ingest, preprocessing, dictionary/regex entities, Neo4j (starting)

## Environment facts (checked 2026-11-21)
- Windows 11, uv 0.11.8, Python 3.12.10 (dev venv pinned to 3.12: scispaCy needs <3.13).
- Docker 29.5.3 installed; daemon was not running at start → launched Docker Desktop.
- Git identity comes from existing git config (not modified).
- Dependency probe (uv lock, py3.12): spaCy 3.8.18, ginza 5.3.1 / ja-ginza 5.3.0
  (needs spaCy >=3.8.16,<4), scispacy 0.6.2 (spaCy >=3.7,<3.9, numpy<2), negspacy 1.1.0
  (spaCy >=3.8). **No conflict**: `[med]` and `[ja]` resolve together on spaCy 3.8.x with
  numpy 1.26.4. Kept as separate extras anyway (CLAUDE.md). scispaCy is marked
  `python_version < "3.13"`.

## M0 plan
1. pyproject (hatchling, src layout), extras med/ja/gliner/embed/neo4j/groq/ollama/dev,
   dependency group `dev` (pytest, ruff, mypy, pre-commit, en_core_web_sm wheel).
2. Package skeleton per prompt 00; `models.py` Pydantic models; `Stage` protocol +
   `Pipeline` with no-op placeholder stages; `config.py` (leankg.toml + `.env` + `LEANKG_*`).
3. `lang/detect.py` kana/CJK ratio heuristic + tests.
4. Tooling: ruff, mypy strict, pytest markers, pre-commit, CI workflow, docker-compose
   Neo4j 5 + APOC, LICENSE (Apache-2.0), README with empty benchmark table, CHANGELOG.
5. Typer CLI stubs: build, eval, review-llm, llm-models, import-owl.

## How to run the checks on THIS machine (important)
Windows **Smart App Control is enforcing** (registry `VerifiedAndReputablePolicyState=1`).
It blocks unsigned native files from the Windows venv: the `.venv\Scripts\*.exe`
launchers (pytest, mypy, leankg) and spaCy's compiled `.pyd` modules. Turning SAC off is
irreversible without reinstalling Windows, so that's the user's call; I didn't do it.
Workaround in use: run everything inside **WSL Ubuntu** on the same checkout, with the
Linux venv outside OneDrive:

```bash
wsl -d Ubuntu
export PATH="$HOME/.local/bin:$PATH" UV_PROJECT_ENVIRONMENT="$HOME/.venvs/leankg" UV_LINK_MODE=copy
cd /mnt/c/Users/itslo/OneDrive/Documents/LeanKG
uv run ruff check . && uv run ruff format --check . && uv run mypy src && uv run pytest -q
```
(uv was installed into the WSL user's `~/.local/bin`.) Git commits are made from Windows git.

## Done
- Kit moved from `leankg-kit/` to repo root; git initialised; kit committed.
- **M0** scaffold: pyproject/extras, models, config, Stage/Pipeline with no-op stages,
  language detection, CLI stubs, tooling (ruff, mypy strict, pytest, pre-commit, CI,
  docker-compose Neo4j+APOC, LICENSE, README, CHANGELOG). 31 tests pass.

## Next
- M1 (see prompts/01_ingest_entities_neo4j.md).

## Decisions log
- D1: `[med]` and `[ja]` stay separate extras although they currently co-resolve.
- D2: Repo `.gitattributes` forces LF so Windows checkouts don't churn line endings
  (git config is not touched).

## Open problems
- Smart App Control blocks spaCy on native Windows Python (see above). Linux/macOS/CI fine.

## Needs you
- Decide whether to keep Smart App Control on (then develop in WSL, as now) or turn it off.
- Replace `OWNER` in `pyproject.toml` URLs with your GitHub user once the repo exists.
