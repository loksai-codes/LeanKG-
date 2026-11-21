# leankg v0.1: rules first, a little Groq — DRAFT

> Draft. The LLM numbers (setups C and D) are placeholders until the Groq runs are done;
> every number below says where it comes from.

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

| Setup | Relation F1 | LLM call rate | Cost / 1,000 docs |
|---|---|---|---|
| C — rules + Groq fallback (gpt-oss-20b) | TBD | TBD | TBD |
| D — Groq on every sentence | TBD | TBD | TBD |

## Try it
`pip install "leankg[ja]"`, then
`leankg build examples/manufacturing --domain manufacturing --llm none`.
