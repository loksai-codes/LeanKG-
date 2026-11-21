# leankg — build progress

> If a session ends or context is cleared: read this file first, then CLAUDE.md, then the
> prompt for the current milestone in `prompts/`. Continue from "Next".

## Current milestone
ALL MILESTONES DONE (M0–M6), including the live Groq run (2026-11-21).

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

- **M3** NER / GLiNER / embedding-linking / chunk-embedding stages, eval harness, seed
  gold fixtures (18 per lang per pack), NCBI/BC5CDR scripts, Label Studio config +
  tasks + converter, CI regression job + baseline. Results so far: see README table.
  - Seed fixtures are author-written and share vocabulary with the dictionaries, so
    entity F1 ≈ 1.0 there is NOT meaningful; relation recall is the informative part.
  - NCBI Disease (400 test sentences, Condition only): setup A finds 0 of 409 mentions —
    the stress dictionary has no genetic-disease vocabulary. Expected; it shows why
    setup B (GLiNER / scispaCy) matters.
  - BC5CDR download returns HTTP 403 for scripted requests → skipped (script kept).
  - **GLiNER and embeddings are not installed yet in the dev venv**: the CPU-torch lock
    kept timing out against PyPI on this network. Setup B numbers therefore = rules +
    spaCy/GiNZA NER only. Retry: add torch CPU index (see git history of pyproject in
    M3 notes) and `uv sync --all-extras`.

- **M4** code complete and tested offline with fake SDK objects / FakeClient (265 unit
  tests; Groq integration tests skip without a key). Hard-case rate with LLM off on the
  seed fixtures: health EN 5.6%, health JA 11.1%, manufacturing EN 16.7%, JA 11.1%.
  - Design question for the user: PLAN.md says never route a sentence that has a
    high-confidence rule hit. In manufacturing, sentences like 「潤滑不足がベアリングの
    焼き付きを引き起こした」 get CAUSED_BY by rule, and the second pair
    (ベアリング HAS_FAILURE_MODE 焼き付き) stays an unverified candidate forever. Routing
    leftover candidate pairs too would raise relation recall but also the call rate.
    Kept the PLAN.md rule for now.
  - Still to do with a key: live integration tests, eval setups C and D, README table,
    second-build cache check.

- **M5** manufacturing pack with no `src/` changes: DATA.md, MaintIE/NHTSA/JA-Wikipedia
  scripts (all verified to download), MaintIE converter, demo_queries.cypher, 100 JA
  sentences per pack for Label Studio (config + pre-annotated tasks). MaintIE (EN, 1,076
  texts): entity F1 0.29 (P 0.78 / R 0.18), relation F1 0.00 — terse work-order style,
  approximate type mapping; NCBI still 0.00 without GLiNER/scispaCy.
  - import-owl skipped in M5 (would be an engine change) → M6.
  - NHTSA info page blocks automated reading; the API itself works. Confirm terms.

- **M6** docs site (mkdocs.yml + pages + Pages workflow; not built locally — mkdocs-material
  isn't installed in the dev venv, CI builds with `--strict`), notebooks (generated by
  scripts/make_notebooks.py, smoke-run end to end against local Neo4j), import-owl,
  version 0.1.0, release workflow (TestPyPI → PyPI trusted publishing), licences.md, blog
  draft, gitleaks: history clean (dir scan hits only numpy tests in the untracked .venv).

- Stopped by Claude Code (system low on memory), not restarted: (a) installing CPU torch +
  gliner + sentence-transformers into the WSL venv (so setup B still = rules + spaCy/GiNZA NER),
  (b) the fresh-venv install audit of the built wheel's extras. Re-run when memory allows:
  `uv pip install --python ~/.venvs/leankg/bin/python --index-url https://download.pytorch.org/whl/cpu torch`
  then `uv pip install --python ~/.venvs/leankg/bin/python gliner sentence-transformers "numpy<2"`.
  Dependency facts already verified by `uv lock`: [med] and [ja] co-resolve on spaCy 3.8.18.

## Live Groq run (2026-11-21) — done
- `leankg llm-models`: gpt-oss-20b served; Llama 3.x no longer listed.
- Integration: 7/7 pass (3 Groq + 4 Neo4j).
- Setups C/D on seed fixtures (relation F1 · LLM call rate · cost/1k docs):
  mf EN A 0.72 → C 0.81 (16.7%, $0.013) → D 0.89 (94.4%, $0.052);
  mf JA A 0.78 → C 0.81 (11.1%, $0.012) → D 0.88 (94.4%, $0.066);
  hs EN A 1.00 → C 0.94 (5.6%, $0.008) → D 0.88 (94.4%, $0.037);
  hs JA A 0.93 → C 0.88 (11.1%, $0.010) → D 0.84 (88.9%, $0.037).
  No run hit the budget. Health "losses" = LLM adds HAS_SYMPTOM for "symptoms common in
  burnout group" sentences that the gold marks as no relation (gold kept as written).
- Cache: second identical build → 0 requests, cache 100%, $0.

## Next
- Label the Japanese gold sets, then re-run A–D on them (`leankg eval --setup X --lang ja`).
- Optionally install GLiNER/embeddings (commands above) and re-run setup B.

## Decisions log
- D1: `[med]` and `[ja]` stay separate extras although they currently co-resolve.
- D2: Repo `.gitattributes` forces LF so Windows checkouts don't churn line endings
  (git config is not touched).

## Open problems
- Smart App Control blocks spaCy on native Windows Python (see above). Linux/macOS/CI fine.

## Needs you
- **Japanese gold labels**: label `domains/<pack>/eval/labelstudio/tasks.ja.json` (100 per
  pack, config.xml alongside) and convert to `domains/<pack>/eval/gold.ja.jsonl` (docs/EVAL.md).
- **GitHub repo**: create `leankg`, push, replace `OWNER` in pyproject.toml and mkdocs.yml.
- **GitHub Pages**: enable Pages (source: GitHub Actions) for the docs workflow.
- **PyPI**: add trusted publishers on test.pypi.org and pypi.org for `release.yml`
  (environments `testpypi`, `pypi`), create those environments, then tag `v0.1.0`.
- Decide: keep Smart App Control on (develop in WSL, as now) or turn it off.
- Decide: route leftover candidate pairs in sentences that already have a confident rule
  hit (higher recall, more LLM calls)? Currently no, per PLAN.md.
- Decide: use MLIT recall data? (terms unclear — not used.)
- Optional: confirm NHTSA data terms (their info page blocks automated reading).
