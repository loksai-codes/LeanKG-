# Writing a domain pack

A pack is a folder of data — no code. leankg finds packs by path, in `./domains/`, in
`LEANKG_DOMAINS_PATH`, in the installed package, or via the `leankg.domains` entry point
(so a pack can ship as its own pip package).

```
domains/<pack>/
  ontology.yaml            # entity + relation types, allowed from/to, labels {en, ja}
  dictionaries/*.csv       # id,type,lang,term,synonyms(|-separated),source
  patterns/entities.jsonl  # regex patterns, each with "lang" (en | ja | *)
  patterns/relations.en.yaml / relations.ja.yaml   # dependency patterns + triggers
  models.yaml              # spaCy / NER label map / GLiNER labels / embedding model
  llm_hints.md, llm_hints.ja.md                    # few-shot examples for the LLM
  eval/fixtures/gold.<lang>.jsonl, eval/gold.<lang>.jsonl
```

Validation errors always name the file and line (`dictionaries/terms_ja.csv:12: unknown
entity type 'Sensr'`).

## ontology.yaml

```yaml
version: 1
name: manufacturing
entities:
  Component:   {labels: {en: Component, ja: 部品}}
  FailureMode: {labels: {en: Failure mode, ja: 故障モード}}
  Cause:       {labels: {en: Cause, ja: 原因}}
relations:
  CAUSED_BY: {from: [FailureMode], to: [Cause, FailureMode], labels: {ja: 原因}}
  ASSOCIATED_WITH: {from: ["*"], to: ["*"], symmetric: true}
```

Entity types may have a `parent`; `"*"` allows any type. Quote descriptions containing
commas in flow mappings (`{description: "a, b"}`).

## Dictionaries
One concept `id` per row group; the same id in an English and a Japanese row is what makes
「ストレス」 and "stress" the same entity in the graph.

```csv
id,type,lang,term,synonyms,source
MF:leak,FailureMode,en,leak,leakage|oil leak,seed
MF:leak,FailureMode,ja,漏れ,油漏れ|オイル漏れ|リーク,seed
```

## Relation patterns
Write dependency patterns from **real parses** — print them first:

```bash
uv run python scripts/dump_parse.py ja "潤滑不足によりベアリングの焼き付きが発生した。"
```

```yaml
dependency:
  - id: ja-niyori-occur
    relations: [{type: CAUSED_BY, reverse: true}]   # head anchor = causer
    pattern:
      - {RIGHT_ID: verb, RIGHT_ATTRS: {LEMMA: {IN: [発生, 生じる]}}}
      - {LEFT_ID: verb, REL_OP: ">", RIGHT_ID: head, RIGHT_ATTRS: {DEP: obl}}
      - {LEFT_ID: head, REL_OP: ">", RIGHT_ID: ni, RIGHT_ATTRS: {DEP: case, LEMMA: に}}
      - {LEFT_ID: ni, REL_OP: ">", RIGHT_ID: yoru, RIGHT_ATTRS: {DEP: fixed, LEMMA: よる}}
      - {LEFT_ID: verb, REL_OP: ">", RIGHT_ID: tail, RIGHT_ATTRS: {DEP: nsubj}}
triggers:
  - id: ja-trig-prevent
    relations: [{type: PREVENTS}]
    position: after        # between | after | any
    window: 4              # tokens (EN) / bunsetsu (JA)
    words: [を防止, を防ぐ, を予防]
```

Tips: quote `"on"`, `"no"`, `"yes"` in YAML lists (the loader rejects YAML booleans);
list several `relations` and let the schema pick the one that fits the entity types;
`reverse: true` swaps head and tail for that relation.

## Learning from the LLM
`leankg review-llm --domain X` groups logged LLM answers by relation and trigger phrase;
`--apply` writes `patterns/relations.<lang>.learned.yaml` and
`dictionaries/learned_<lang>.csv`, which the loader merges automatically. Review them
before committing.

## From an existing ontology
`leankg import-owl ontology.ttl --out ontology.yaml --dictionary dictionaries/owl.csv`
converts OWL classes, object properties (domain/range) and individuals, keeping `@ja`
labels.
