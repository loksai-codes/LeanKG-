# Japanese support — design

Japanese is first-class from milestone 1, not a late add-on. The main differences from
English: no spaces between words, tokenizers disagree on word boundaries, SOV word order
with particles (が/を/に/で/により), mixed scripts (kanji, hiragana, katakana, full-width
Latin), and none of the English medical tools (scispaCy, negspaCy) work on it.

## 1. LanguageProfile
Everything language-specific sits behind one interface in `src/leankg/lang/`:

```python
class LanguageProfile(Protocol):
    code: str                                  # "en" | "ja"
    def load_nlp(self, models_cfg) -> Language
    def normalize(self, text: str) -> str      # matching key
    def split_sentences(self, doc) -> Iterable[Span]
    def negation_hedge(self, span, head, tail) -> tuple[bool, bool, float]
    def dep_patterns(self, pack) -> list[DepPattern]   # loads patterns/relations.<code>.yaml
```

`EnglishProfile` uses spaCy `en_core_web_sm` (+ scispaCy for med packs) and negspaCy.
`JapaneseProfile` uses GiNZA `ja_ginza` (fast CPU model; `ja_ginza_electra` optional for accuracy).

## 2. Language detection
Per document, then per chunk (Japanese manuals often contain English part names):
a cheap heuristic is enough — share of hiragana/katakana/CJK chars > 0.2 → `ja`.
No extra dependency. Mixed docs are split by chunk and each chunk keeps its own `lang`.

## 3. Normalization (the biggest accuracy lever)
`JapaneseProfile.normalize`: Unicode NFKC (full-width → half-width ASCII, half-width kana →
full-width) → `jaconv.hira2kata` (so ひずみ and ヒズミ match) → strip long-vowel mark
variants (ー/－/‐) → lowercase Latin. Apply the same function to dictionary terms at
load time and to text at match time.

## 4. Entity extraction
- **Dictionary match:** don't rely on token-based PhraseMatcher for Japanese — Sudachi may
  split 油圧ポンプ differently from how the dictionary term was tokenized. Instead run
  character-level Aho-Corasick (`pyahocorasick`) on normalized text, longest match wins,
  then map to tokens with `doc.char_span(..., alignment_mode="expand")`. Keep a
  normalized→original offset map since NFKC can change string length.
- **Regex:** patterns are per language in `patterns/entities.jsonl` with a `lang` field
  (e.g. 部品番号, エラーコード E-1234, 用量 5mg/5ｍｇ after normalization).
- **Statistical NER:** GiNZA's NER gives ORG/DATE/PRODUCT etc. for Japanese; scispaCy is
  EN only.
- **GLiNER:** use a multilingual checkpoint (e.g. `urchade/gliner_multi-v2.1` — check the
  current best one and its licence). Test whether English labels ("FailureMode") or
  Japanese labels ("故障モード") give better recall on the JA gold set; make it a pack setting.
- **Sudachi user dictionary (later):** add domain compounds so they stay one token.

## 5. Entity linking (cross-lingual)
- ontology.yaml carries labels per language; dictionaries CSV has a `lang` column.
- Exact/synonym → RapidFuzz on normalized strings (use `fuzz.ratio` on characters, not
  token-based scorers, for JA) → embedding similarity.
- Use one **multilingual** sentence-transformers model for both linking and chunk
  embeddings (e.g. `intfloat/multilingual-e5-small` or `paraphrase-multilingual-MiniLM-L12-v2`),
  so a Japanese mention can link to an English-labelled ontology ID and Neo4j vector
  search works across languages. Record the model name in the graph metadata.

## 6. Relation extraction
- `patterns/relations.ja.yaml`: DependencyMatcher patterns over GiNZA's UD parse. Typical
  shapes:
  - `X が Y を 引き起こす` → head verb 引き起こす, `nsubj`=X, `obj`=Y → X CAUSES Y
  - `X により/によって Y が 発生する` → `obl` with case marker により = cause
  - `Y は X が 原因 で ある` / `X に 起因 する`
  - `X は Y を 軽減する/改善する/減らす` → REDUCES
  - `X は Y の 一部` / `Y の X` (careful: の is very ambiguous → low confidence only)
- Trigger lexicon per relation in Japanese: 原因, 起因, 引き起こす, 発生, 誘発, 悪化,
  軽減, 改善, 予防, 防止, 交換, 修理, 漏れ, 検出, 検知 …
- GiNZA bunsetsu spans (`ginza.bunsetu_spans`) are useful for typed co-occurrence: only
  pair entities whose bunsetsu are linked in the parse, not every pair in the sentence.

## 7. Negation and hedging (Japanese rules replace negspaCy)
- Negation: auxiliary ない/ず/ぬ/ません/なかった/なし attached to the relation's predicate
  (check `token.morph` for `Polarity=Neg` and the aux lemma), plus 否定, 認められない,
  見られない.
- Hedging: かもしれない, 可能性がある, と考えられる, と思われる, 恐れがある, 示唆, らしい,
  ようだ, 疑い.
- Double negatives / long-distance cases (〜ないとは言えない) → mark `complex=True` and route
  to the LLM.

## 8. Neo4j
- Entity: `name` (canonical, from ontology preferred label), `name_ja`, `aliases`
  (list of `{text, lang}` flattened to `aliases_en`/`aliases_ja` arrays), `lang_seen`.
- Chunk: `lang` property.
- Full-text index on entity names/aliases with the `cjk` analyzer so Japanese search works.

## 9. Evaluation
- Each pack has `eval/gold.en.jsonl` and `eval/gold.ja.jsonl`. Report the A/B/C/D table
  per language.
- CI fixtures: 10–20 sentences per language per pack, LLM off, fail if F1 drops > 2 pts.

## 10. Data sources (verify licence and terms before use)
- Japanese Wikipedia articles on TPS concepts (トヨタ生産方式, 自働化, アンドン, ポカヨケ,
  なぜなぜ分析, カイゼン) — CC BY-SA; good for seeding manufacturing pack labels.
- Japanese government car recall/defect information (MLIT publishes recall notices) —
  check reuse terms.
- Japanese public health pages (e.g. MHLW) for the health pack — check terms.
- Hand-label ~100 JA sentences per pack in Label Studio / doccano.

## Dependency note
GiNZA 5.2.0 (latest at time of writing) targets spaCy 3.7. scispaCy also pins spaCy
versions. Keep JA in the `leankg[ja]` extra and, if uv can't resolve both together,
document two install profiles (`[med]` and `[ja]`) instead of downgrading silently.
