# health_stress domain pack

Psychological stress, its health effects, interventions and measurement, in English and
Japanese.

**Data status:** every dictionary row, pattern and fixture sentence in this pack is
**hand-written seed data** by the leankg authors, for illustration and tests. It is not a
curated clinical terminology and must not be used for medical decisions.

| File | Contents |
|---|---|
| `ontology.yaml` | 7 entity types, 6 relations, EN/JA labels |
| `dictionaries/terms_{en,ja}.csv` | `id,type,lang,term,synonyms,source` (synonyms separated by `|`) |
| `patterns/entities.jsonl` | regex entity patterns with `lang` |
| `patterns/relations.{en,ja}.yaml` | dependency patterns + trigger lexicon |
| `models.yaml` | per-language spaCy / GLiNER / embedding model names |
| `llm_hints.md`, `llm_hints.ja.md` | few-shot examples for the LLM fallback |
| `eval/` | gold data and CI fixtures |
