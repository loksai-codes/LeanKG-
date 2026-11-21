# leankg v0.1: rules first, a little Groq — DRAFT

> Draft. Numbers come from `leankg eval` on small hand-written fixtures (18 sentences per
> language per pack) with Groq `openai/gpt-oss-20b`; treat them as a smoke test, not a
> leaderboard.

Most "documents to knowledge graph" demos send every sentence to a large model. That
works, but you pay for every sentence, you wait for every sentence, and you get a
different graph each time you run it. leankg tries the opposite: let cheap, deterministic
NLP do what it is good at, and ask an LLM only about the sentences the rules can't settle.

## What the rules do
For each sentence leankg finds entities from the domain pack's dictionaries (character-
level matching for Japanese, so 油圧ポンプ matches even when the tokenizer splits it),
regexes, spaCy/GiNZA NER and, optionally, GLiNER. Relations come from dependency patterns
written against real parses, a trigger lexicon, and typed co-occurrence. Negation and
hedging rules mark 「運動はストレスを軽減しなかった」 as *negative evidence* rather than dropping
it or, worse, storing it as a fact.

## When the LLM is asked
A sentence becomes a *hard case* only if it has entities the schema allows to relate but no
confident rule hit, an ambiguous link, a low-confidence rule triple, or tricky negation
(〜ないとは言えない). The LLM sees the sentence, a numbered entity list and the allowed
relation types, and answers with indices only under a strict JSON schema. Answers are
cached, near-duplicates are deduplicated, batches are grouped by language, and a budget cap
degrades to "unverified" instead of failing.

## Numbers so far
On the hand-written seed fixtures (18 sentences per language per pack; optimistic because
the same people wrote the dictionaries):

| Pack | Lang | Rules only: relation F1 | Hard-case rate (would go to the LLM) |
|---|---|---|---|
| health_stress | en | 1.00 | 5.6% |
| health_stress | ja | 0.93 | 11.1% |
| manufacturing | en | 0.72 | 16.7% |
| manufacturing | ja | 0.78 | 11.1% |

On public data the picture is more sober: on MaintIE's 1,076 maintenance work orders,
rules-only entity F1 is 0.29 (precision 0.78, recall 0.18) under an approximate mapping
of MaintIE's scheme, and the stress pack finds none of NCBI Disease's genetic diseases —
which is exactly what a dictionary should do, and why setup B adds GLiNER.

With Groq (gpt-oss-20b) on the same fixtures:

| Pack / lang | Rules only (A) | Rules + LLM fallback (C) | LLM only (D) |
|---|---|---|---|
| manufacturing / en | 0.72 · 0% · $0 | 0.81 · 16.7% · $0.013 | 0.89 · 94.4% · $0.052 |
| manufacturing / ja | 0.78 · 0% · $0 | 0.81 · 11.1% · $0.012 | 0.88 · 94.4% · $0.066 |
| health_stress / en | 1.00 · 0% · $0 | 0.94 · 5.6% · $0.008 | 0.88 · 94.4% · $0.037 |
| health_stress / ja | 0.93 · 0% · $0 | 0.88 · 11.1% · $0.010 | 0.84 · 88.9% · $0.037 |

(relation F1 · share of sentences sent to the LLM · cost per 1,000 docs)

Two honest readings. In manufacturing the fallback buys part of what an LLM-only run gets
for about a sixth of the calls; the rest is lost because sentences with one confident rule
hit are never sent, which is a design choice worth revisiting. In the health pack the rules
were already right and the LLM mostly added relations the gold labels don't accept (it
reads "headache and fatigue were common in the burnout group" as HAS_SYMPTOM). Rules-first
isn't automatically more accurate; it is cheaper, repeatable — the second run cost $0 from
the cache — and it tells you exactly where the LLM was used.

## Try it
`pip install "leankg[ja]"`, then
`leankg build examples/manufacturing --domain manufacturing --llm none`.
