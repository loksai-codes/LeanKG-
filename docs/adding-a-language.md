# Adding a language — Japanese as the worked example

Adding a language = **a `LanguageProfile` + pack files**. Stages never branch on the
language; they call the profile. Japanese was built this way from the start.

## 1. The profile (`src/leankg/lang/ja.py`)

| Member | Japanese implementation | Why |
|---|---|---|
| `load_nlp()` | GiNZA `ja_ginza`; fallback: blank pipeline + script-run tokenizer | works without the `[ja]` extra (no parse) |
| `normalize()` / `normalize_map()` | NFKC → hiragana→katakana → drop long-vowel marks after kana → lowercase, with an offset map | ﾓｰﾀｰ = モーター = モータ, ひずみ = ヒズミ; NFKC changes string length |
| `split_sentences()` | split after 。！？!?． (keep closing brackets) and on newlines | no spaces between words |
| `dict_strategy` | `"chars"`: Aho-Corasick on normalized characters | Sudachi may split 油圧ポンプ differently from the dictionary |
| `accept_dict_key()` | single characters only if kanji (錆, 煙) | single kana are too ambiguous |
| `fuzzy_scorer` | `"ratio"` (character ratio) | token-based scorers assume spaces |
| `units()` | bunsetsu (`ginza.bunsetu_spans`), else tokens | trigger windows |
| `connected()` | bunsetsu linked in the parse (or share a head) | restricts co-occurrence pairs |
| `negation_hedge()` | `lang/ja_rules.py`: scope = predicate after the later argument; ない/なかった/ません…, hedges かもしれない/可能性…, complex ないとは言えない | negspaCy is English-only |
| `trigger_phrase()` | predicate after the arguments (≈ bunsetsu head) | for `review-llm` |

Register it in `lang/base.py:make_profile` and the language detector picks it up when a
chunk's kana/CJK ratio is above 0.2.

## 2. Pack files
- `labels.ja` for every entity and relation type in `ontology.yaml`;
- `dictionaries/terms_ja.csv` sharing concept ids with the English rows;
- `patterns/entities.jsonl` entries with `"lang": "ja"` — use `(?<![A-Za-z0-9])`
  instead of `\b` (kana are word characters in Python regex);
- `patterns/relations.ja.yaml` written from GiNZA dumps (`scripts/dump_parse.py ja …`).
  GiNZA facts we relied on: サ変 nouns as predicates are `VERB` + aux する; 「XがYの原因である」
  → 原因 with `nsubj` X and `nmod` Y; により → `obl` + `case` に + `fixed` よる; negation is
  the `AUX` lemma ない (no `Polarity=Neg` feature);
- `llm_hints.ja.md` few-shot examples (attached when a batch has Japanese cases).

## 3. Gold data and tests
Tiny fixtures per language for CI (`eval/fixtures/gold.ja.jsonl`), relation test sentences
including negated and hedged ones, and an independently labelled gold set via Label Studio
(`leankg labelstudio config --lang ja` uses character-level spans).
