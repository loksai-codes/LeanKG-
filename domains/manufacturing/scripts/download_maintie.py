"""Download MaintIE gold (Bikaun et al., MIT licence) and convert it to leankg gold JSONL.

Source: https://github.com/nlp-tlp/maintie (data/gold_release.json, 1,076 maintenance
work-order texts). Data is written to ./data/maintie/ (git-ignored), never committed.

Type mapping (approximate — MaintIE's scheme is finer and different, see DATA.md):
  PhysicalObject/SensingObject/*                 -> Sensor
  PhysicalObject/* (other)                       -> Component
  State|Process|Property/Undesirable*            -> FailureMode
  Activity/MaintenanceActivity|SupportingActivity -> MaintenanceAction
Relation mapping:
  hasPart(whole, part)                           -> PART_OF(part, whole)
  hasPatient(FailureMode, Component)             -> HAS_FAILURE_MODE(Component, FailureMode)
  hasPatient(MaintenanceAction, Component)       -> FIXED_BY(Component, MaintenanceAction)
  everything else                                -> dropped

Usage: uv run python domains/manufacturing/scripts/download_maintie.py
Then:  uv run leankg eval --domain manufacturing --setup A --lang en --gold data/maintie/gold.en.jsonl
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path
from typing import Any

from leankg.eval.gold import GoldEntity, GoldExample, GoldRelation, dump_gold

URL = "https://raw.githubusercontent.com/nlp-tlp/maintie/main/data/gold_release.json"
OUT = Path("data/maintie")


def map_type(t: str) -> str | None:
    parts = t.split("/")
    top = parts[0]
    sub = parts[1] if len(parts) > 1 else ""
    if top == "PhysicalObject":
        return "Sensor" if sub == "SensingObject" else "Component"
    if top in ("State", "Process", "Property") and sub.startswith("Undesirable"):
        return "FailureMode"
    if top == "Activity" and sub in ("MaintenanceActivity", "SupportingActivity"):
        return "MaintenanceAction"
    return None


def convert(records: list[dict[str, Any]]) -> list[GoldExample]:
    out: list[GoldExample] = []
    for n, rec in enumerate(records):
        tokens: list[str] = rec["tokens"]
        starts, pos = [], 0
        for tok in tokens:
            starts.append(pos)
            pos += len(tok) + 1
        text = " ".join(tokens)
        index: dict[int, int] = {}
        ents: list[GoldEntity] = []
        for i, e in enumerate(rec.get("entities", [])):
            typ = map_type(e["type"])
            if typ is None or e["end"] > len(tokens) or e["start"] >= e["end"]:
                continue
            s = starts[e["start"]]
            end = starts[e["end"] - 1] + len(tokens[e["end"] - 1])
            if any(s < x.end and x.start < end for x in ents):
                continue
            index[i] = len(ents)
            ents.append(GoldEntity(start=s, end=end, text=text[s:end], type=typ))
        rels: list[GoldRelation] = []
        for r in rec.get("relations", []):
            if r["head"] not in index or r["tail"] not in index:
                continue
            h, t = index[r["head"]], index[r["tail"]]
            ht, tt = ents[h].type, ents[t].type
            if r["type"] == "hasPart" and ht == tt == "Component":
                rels.append(GoldRelation(head=t, tail=h, type="PART_OF"))
            elif r["type"] == "hasParticipant/hasPatient" and tt == "Component":
                if ht == "FailureMode":
                    rels.append(GoldRelation(head=t, tail=h, type="HAS_FAILURE_MODE"))
                elif ht == "MaintenanceAction":
                    rels.append(GoldRelation(head=t, tail=h, type="FIXED_BY"))
        out.append(GoldExample(id=f"maintie-{n:04d}", lang="en", text=text, entities=ents,
                               relations=rels, source="maintie"))  # fmt: skip
    return out


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    raw = OUT / "gold_release.json"
    if not raw.exists():
        print(f"downloading {URL}")
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "leankg-dataset-script"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                raw.write_bytes(resp.read())
        except OSError as exc:
            print(f"download failed: {exc}", file=sys.stderr)
            return 1
    gold = convert(json.loads(raw.read_text(encoding="utf-8")))
    path = dump_gold(gold, OUT / "gold.en.jsonl")
    print(f"wrote {path}: {len(gold)} texts, {sum(len(g.entities) for g in gold)} entities, "
          f"{sum(len(g.relations) for g in gold)} relations")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
