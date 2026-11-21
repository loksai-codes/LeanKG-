# M6 — Polish and publish (paste into Claude Code)

1. MkDocs Material site: getting started, architecture (pipeline diagram), writing a domain
   pack, adding a language (use JA as the worked example), LLM cost controls, Groq setup,
   benchmark results. GitHub Pages workflow.
2. Notebooks: `health_stress_en.ipynb` and `manufacturing_ja.ipynb` (build a small graph,
   show the RunReport, run 3 Cypher queries incl. a Japanese one). They must run with
   `--llm none` so anyone can execute them without a key.
3. README: goal, 30-second quick start, architecture picture, benchmark table (per
   language, with LLM call rate and cost per 1,000 docs), limitations, roadmap.
4. Release: version 0.1.0, CHANGELOG, build with `uv build`, a release workflow using PyPI
   trusted publishing (I'll configure the PyPI side), test on TestPyPI first.
5. Audit: no secrets, no datasets committed, licences of every model and dataset listed in
   `docs/licences.md`, all extras install cleanly in a fresh venv (report any spaCy pin
   conflict between `[med]` and `[ja]`).
6. Draft a short blog post (`docs/blog/leankg-v0.1.md`) about rules + a little Groq vs
   LLM-only, with the numbers from the table.
