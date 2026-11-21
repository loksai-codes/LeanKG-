# leankg — build progress

> If a session ends or context is cleared: read this file first, then CLAUDE.md, then the
> prompt for the current milestone in `prompts/`. Continue from "Next".

## Current milestone
M3 — NER, GLiNER, linking, evaluation harness (starting)

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

## M1 plan
1. `lang/text.py`: char-group normalization with an offset map (NFKC can change length;
   half-width kana + voiced marks are grouped first). `EnglishProfile` (en_core_web_sm,
   blank fallback, rule sentence splitter, plural variants) and `JapaneseProfile`
   (ja_ginza; fallback script-run tokenizer so JA works without the extra; splitter on
   。！？ and newlines; normalize = NFKC → hira2kata → drop long-vowel marks after kana →
   lowercase).
2. Ingest: loaders TXT/MD, HTML (trafilatura), PDF (pypdf), CSV (configurable text/id
   column), JSONL; clean whitespace; detect lang per doc and per paragraph; sentence-aware
   chunker (800 EN / 400 JA from config), chunk breaks on language change.
3. DomainPack: ontology.yaml, dictionaries/*.csv, patterns/entities.jsonl, models.yaml,
   validated with `file:line` errors; loader resolves path → ./domains → repo → bundled →
   entry points.
4. Dictionary stage (EN PhraseMatcher LOWER + plural variants; JA Aho-Corasick on
   normalized chars, longest-match greedy, offset map back). Regex stage on NFKC text.
5. Basic linking (dictionary id → entity id; others by type+normalized text) so entities
   exist; full linking is M3. `graph.py` merges entities/triples across docs.
6. Exporters JSON/CSV/NetworkX(GraphML) + Neo4j writer (constraints, UNWIND…MERGE
   batches of 1000, `:Entity:<Type>`, name_ja/aliases arrays, CJK full-text indexes).
7. Seed packs (hand-written, labelled as such). `leankg build` end to end + RunReport.

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

- **M1** ingest/lang profiles/pack loader/dictionary+regex entities/basic linking/
  exporters/Neo4j writer/`leankg build`. 104 unit tests + 3 Neo4j integration tests pass
  (Docker Neo4j 5 running; WSL reaches it on localhost:7687). JA full-text (cjk analyzer)
  returns hits for ストレス / 不眠.
  - Note: the "50 MedlinePlus pages + 20 JA pages" target from PLAN.md is replaced by the
    hand-written `examples/` set for now (dataset download scripts come in M3/M5).

- **M2** plan → done: dependency stage (patterns from real parses, saved under
  tests/fixtures/parses), trigger stage (type-aware), cooc stage, negation stage
  (lang/en_rules.py, lang/ja_rules.py), validate stage, relation YAMLs for both packs and
  both languages. 207 unit tests + 4 Neo4j integration tests pass (typed relationships
  for EN and JA, negative evidence stored with `negated: true`).
  - Finding: en_core_web_sm misparses short headline-style sentences ("X treats Y" →
    noun compound); the trigger lexicon covers those.
  - Finding: GiNZA has no `Polarity=Neg`; negation is the AUX lemma ない/ず/ぬ.

## Next
- M3 (see prompts/03_models_linking_eval.md).

## Decisions log
- D1: `[med]` and `[ja]` stay separate extras although they currently co-resolve.
- D2: Repo `.gitattributes` forces LF so Windows checkouts don't churn line endings
  (git config is not touched).

## Open problems
- Smart App Control blocks spaCy on native Windows Python (see above). Linux/macOS/CI fine.

## Needs you
- Decide whether to keep Smart App Control on (then develop in WSL, as now) or turn it off.
- Replace `OWNER` in `pyproject.toml` URLs with your GitHub user once the repo exists.
