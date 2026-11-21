# manufacturing pack — data sources and terms

Nothing below is committed to the repository; the scripts in `scripts/` download into
`./data/` (git-ignored). Check each source's current terms before redistributing anything.

| Source | What | Licence / terms (checked 2026-11-21) | Script | Status |
|---|---|---|---|---|
| **MaintIE** (Bikaun et al., nlp-tlp/maintie) | 1,076 gold-annotated maintenance work-order texts (EN) | MIT (repository README/LICENSE) | `scripts/download_maintie.py` → `data/maintie/gold.en.jsonl` | works |
| **NHTSA complaints API** | Vehicle owner complaints (EN), with component field | US government (NHTSA) public data; the NHTSA datasets page refused automated reading, so confirm terms at nhtsa.gov. Texts are written by the public: may contain personal details — keep local | `scripts/download_nhtsa.py` → `data/nhtsa/complaints.csv` | API works |
| **Japanese Wikipedia** TPS articles (トヨタ生産方式, 自働化, アンドン, ポカヨケ, なぜなぜ分析, カイゼン, …) | Plain text (JA) | CC BY-SA 4.0 (+ GFDL); attribution + share-alike required | `scripts/download_ja_wikipedia_tps.py` → `data/ja_wikipedia_tps/*.txt` | works |
| MLIT recall/defect notices (国土交通省 リコール情報) | JA recall texts | **Terms unclear for bulk reuse** — not used; needs the user's decision | — | not used |
| IOF maintenance ontology | OWL | not imported: `leankg import-owl` is not implemented yet and M5 forbids engine changes (planned for M6) | — | skipped |

## MaintIE → leankg mapping (approximate)
MaintIE's scheme (PhysicalObject / State / Process / Activity / Property, 224 leaf types)
is different from this pack's ontology. The converter maps:

- `PhysicalObject/SensingObject/*` → Sensor; other `PhysicalObject/*` → Component
  (MaintIE doesn't separate machines from components);
- `State|Process|Property/Undesirable*` → FailureMode;
- `Activity/MaintenanceActivity|SupportingActivity` → MaintenanceAction;
- `hasPart(whole, part)` → PART_OF(part, whole);
  `hasPatient(FailureMode, Component)` → HAS_FAILURE_MODE(Component, FailureMode);
  `hasPatient(MaintenanceAction, Component)` → FIXED_BY(Component, MaintenanceAction);
- everything else (desirable states, `isA`, `contains`, `hasAgent`, `hasProperty`) is dropped.

Because of this mapping and MaintIE's terse, lower-cased work-order style ("replace engine
oil filter"), scores on MaintIE measure transfer to a different annotation scheme, not
this pack's ceiling.

## Hand-written data in this pack
Dictionaries, patterns, fixture sentences, LLM hints and `eval/labelstudio/sentences.ja.txt`
were written by the leankg authors. They are illustrative, not authoritative.
