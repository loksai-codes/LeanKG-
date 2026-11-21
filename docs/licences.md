# Licences of models and datasets

leankg itself is Apache-2.0. It downloads or loads the following third-party resources;
check their current terms before redistribution. Nothing below is committed to the
repository (datasets are fetched by scripts into the git-ignored `data/` folder).

## Models

| Resource | Used for | Licence (as published by the authors) |
|---|---|---|
| spaCy `en_core_web_sm` 3.8 | EN tokenization, parse, NER | MIT |
| GiNZA `ja_ginza` 5.3 (+ SudachiPy / SudachiDict-core) | JA tokenization, parse, NER, bunsetsu | MIT (GiNZA); Apache-2.0 (SudachiPy, SudachiDict) |
| scispaCy models (e.g. `en_ner_bc5cdr_md`), optional | EN biomedical NER | Apache-2.0 (scispaCy); models trained on BC5CDR — check BioCreative terms |
| negspaCy termsets, optional | EN negation cues | MIT |
| GLiNER `urchade/gliner_multi-v2.1`, optional | zero-shot multilingual NER | Apache-2.0 (model card); verify before commercial use |
| `intfloat/multilingual-e5-small`, optional | linking + chunk embeddings | MIT |
| Groq-hosted `openai/gpt-oss-20b` / `-120b`, optional | LLM fallback | Apache-2.0 weights; use via Groq is governed by Groq's terms of service |

## Datasets

| Dataset | Script | Licence / terms |
|---|---|---|
| NCBI Disease corpus | `scripts/download_ncbi_disease.py` | released by NCBI for research use; cite Doğan et al. 2014 |
| BC5CDR (BioCreative V CDR) | `scripts/download_bc5cdr.py` | research use; the host refused scripted download (HTTP 403) when tested |
| MaintIE | `domains/manufacturing/scripts/download_maintie.py` | MIT |
| NHTSA complaints | `domains/manufacturing/scripts/download_nhtsa.py` | US government public data; texts may contain personal details — keep local |
| Japanese Wikipedia (TPS articles) | `domains/manufacturing/scripts/download_ja_wikipedia_tps.py` | CC BY-SA 4.0 (+ GFDL): attribution and share-alike |
| MLIT recall notices | not used | terms unclear for bulk reuse |

## Hand-written data
Dictionaries, patterns, fixture sentences, examples and LLM hints in this repository were
written by the leankg authors and are covered by the project licence (Apache-2.0).
