"""Gold-standard format (JSONL, one sentence or short passage per line).

```json
{"id": "hs-en-001", "lang": "en", "text": "Chronic stress increases the risk of insomnia.",
 "entities": [
   {"start": 0, "end": 14, "type": "Stressor", "id": "HS:chronic_stress"},
   {"text": "insomnia", "type": "Condition", "id": "HS:insomnia"}
 ],
 "relations": [{"head": 0, "tail": 1, "type": "INCREASES_RISK_OF", "negated": false}],
 "source": "seed"}
```

* ``entities[].start/end`` are character offsets into ``text``. When omitted, ``text`` (the
  surface) is located in the sentence: the first occurrence after the previous entity, or
  the n-th occurrence with ``"occurrence": n`` (1-based).
* ``entities[].id`` is the ontology concept id (optional; used for linking accuracy).
* ``relations[].head/tail`` index into ``entities``. ``negated`` defaults to false.
* ``source`` says where the line came from (``seed`` = hand-written by the leankg authors,
  ``ncbi``, ``bc5cdr``, ``maintie``, ``labelstudio`` …).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GoldEntity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start: int = -1
    end: int = -1
    text: str = ""
    type: str
    id: str | None = None
    occurrence: int | None = None


class GoldRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    head: int
    tail: int
    type: str
    negated: bool = False


class GoldExample(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    lang: str
    text: str
    entities: list[GoldEntity] = Field(default_factory=list)
    relations: list[GoldRelation] = Field(default_factory=list)
    source: str = ""

    @model_validator(mode="after")
    def _resolve_offsets(self) -> GoldExample:
        cursor = 0
        for i, ent in enumerate(self.entities):
            if ent.start < 0 or ent.end < 0:
                if not ent.text:
                    raise ValueError(f"entity {i} needs start/end or text")
                if ent.occurrence:
                    pos = -1
                    for _ in range(ent.occurrence):
                        pos = self.text.find(ent.text, pos + 1)
                else:
                    pos = self.text.find(ent.text, cursor)
                    if pos < 0:
                        pos = self.text.find(ent.text)
                if pos < 0:
                    raise ValueError(f"entity {i} text {ent.text!r} not found in {self.text!r}")
                ent.start, ent.end = pos, pos + len(ent.text)
            if not (0 <= ent.start < ent.end <= len(self.text)):
                raise ValueError(f"entity {i} offsets {ent.start}-{ent.end} out of range")
            surface = self.text[ent.start : ent.end]
            if ent.text and ent.text != surface:
                raise ValueError(f"entity {i}: text {ent.text!r} != text[start:end] {surface!r}")
            ent.text = surface
            cursor = ent.end
        n = len(self.entities)
        for r in self.relations:
            if not (0 <= r.head < n and 0 <= r.tail < n) or r.head == r.tail:
                raise ValueError(f"relation {r} references a missing entity")
        return self


def load_gold(path: str | Path) -> list[GoldExample]:
    """Load a gold JSONL file. Errors mention the line number."""
    p = Path(path)
    out: list[GoldExample] = []
    for line_no, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        try:
            out.append(GoldExample.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValueError) as exc:
            raise ValueError(f"{p}:{line_no}: {exc}") from exc
    return out


def dump_gold(examples: list[GoldExample], path: str | Path) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="\n") as fh:
        for ex in examples:
            data = ex.model_dump(exclude_none=True)
            for ent in data["entities"]:
                ent.pop("occurrence", None)
            fh.write(json.dumps(data, ensure_ascii=False) + "\n")
    return p
