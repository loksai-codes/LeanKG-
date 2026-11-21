"""Label Studio helpers: labeling config, task files and export → gold conversion.

Workflow (docs/EVAL.md):

1. ``leankg labelstudio config --domain X > config.xml`` — paste into a Label Studio
   project (Settings → Labeling Interface → Code). Uses ``granularity="symbol"`` so spans
   can start/end anywhere in Japanese text.
2. ``leankg labelstudio tasks --domain X --lang ja sentences.txt --out tasks.json
   [--preannotate]`` — import into the project. ``--preannotate`` adds leankg's own output
   as *predictions* to speed up labeling (review every one; don't accept blindly).
3. Label entities (span + type) and relations (drag from head to tail, pick the relation
   label, add ``negated`` when the sentence denies it). Export → JSON.
4. ``leankg labelstudio convert export.json --lang ja --out domains/X/eval/gold.ja.jsonl``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from xml.sax.saxutils import quoteattr

from leankg.domain.pack import DomainPack
from leankg.eval.gold import GoldEntity, GoldExample, GoldRelation

NEGATED_LABEL = "negated"
_COLORS = (
    "#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#46a5a5", "#f032e6",
    "#9a6324", "#808000", "#000075", "#469990", "#aa6e28",
)  # fmt: skip


def labeling_config(pack: DomainPack, lang: str = "en") -> str:
    """Label Studio XML: entity labels + relation labels (+ ``negated``) from the ontology."""
    labels = []
    for i, (name, edef) in enumerate(pack.ontology.entities.items()):
        hint = edef.labels.get(lang) or edef.labels.get("en") or name
        labels.append(
            f"    <Label value={quoteattr(name)} hint={quoteattr(hint)} "
            f"background={quoteattr(_COLORS[i % len(_COLORS)])}/>"
        )
    rels = [f"    <Relation value={quoteattr(r)}/>" for r in pack.ontology.relations]
    rels.append(f"    <Relation value={quoteattr(NEGATED_LABEL)}/>")
    return "\n".join(
        [
            "<View>",
            f"  <Header value={quoteattr(f'leankg / {pack.name} / {lang}')}/>",
            '  <Relations choice="multiple">',
            *rels,
            "  </Relations>",
            '  <Labels name="label" toName="text">',
            *labels,
            "  </Labels>",
            '  <Text name="text" value="$text" granularity="symbol"/>',
            "</View>",
        ]
    )


def _region(rid: str, start: int, end: int, text: str, label: str) -> dict[str, Any]:
    return {
        "id": rid,
        "from_name": "label",
        "to_name": "text",
        "type": "labels",
        "value": {"start": start, "end": end, "text": text, "labels": [label]},
    }


def make_tasks(
    texts: Iterable[str],
    lang: str,
    prefix: str,
    predictions: list[GoldExample] | None = None,
) -> list[dict[str, Any]]:
    """Label Studio task dicts; optional pre-annotations as ``predictions``."""
    tasks = []
    for i, text in enumerate(texts, start=1):
        task: dict[str, Any] = {
            "data": {"id": f"{prefix}-{lang}-{i:03d}", "lang": lang, "text": text}
        }
        if predictions is not None:
            pred = predictions[i - 1]
            result: list[dict[str, Any]] = [
                _region(f"e{k}", e.start, e.end, e.text, e.type)
                for k, e in enumerate(pred.entities)
            ]
            for r in pred.relations:
                labels = [r.type, *([NEGATED_LABEL] if r.negated else [])]
                result.append(
                    {"from_id": f"e{r.head}", "to_id": f"e{r.tail}", "type": "relation",
                     "direction": "right", "labels": labels}
                )  # fmt: skip
            task["predictions"] = [{"model_version": "leankg", "result": result}]
        tasks.append(task)
    return tasks


def _pick_annotation(task: dict[str, Any]) -> list[dict[str, Any]] | None:
    anns = [a for a in task.get("annotations", []) if not a.get("was_cancelled")]
    if not anns:
        return None
    latest = max(anns, key=lambda a: str(a.get("updated_at") or a.get("created_at") or ""))
    result: list[dict[str, Any]] = latest.get("result", [])
    return result


def convert_export(
    export: list[dict[str, Any]], lang: str | None = None, source: str = "labelstudio"
) -> tuple[list[GoldExample], list[str]]:
    """Label Studio JSON export → gold examples. Returns (examples, warnings)."""
    out: list[GoldExample] = []
    warnings: list[str] = []
    for n, task in enumerate(export, start=1):
        data = task.get("data", {})
        text = data.get("text", "")
        tid = str(data.get("id") or f"ls-{task.get('id', n)}")
        result = _pick_annotation(task)
        if result is None:
            warnings.append(f"{tid}: no (non-cancelled) annotation; skipped")
            continue
        regions = [r for r in result if r.get("type") == "labels"]
        regions.sort(key=lambda r: (r["value"]["start"], r["value"]["end"]))
        index: dict[str, int] = {}
        entities: list[GoldEntity] = []
        for r in regions:
            v = r["value"]
            if not v.get("labels"):
                continue
            surface = text[v["start"] : v["end"]]
            if v.get("text") and v["text"] != surface:
                warnings.append(f"{tid}: region text {v['text']!r} != {surface!r}; using offsets")
            index[r["id"]] = len(entities)
            entities.append(
                GoldEntity(start=v["start"], end=v["end"], text=surface, type=v["labels"][0])
            )
        relations: list[GoldRelation] = []
        for r in result:
            if r.get("type") != "relation":
                continue
            if r.get("from_id") not in index or r.get("to_id") not in index:
                warnings.append(f"{tid}: relation to an unknown region; skipped")
                continue
            labels = [lb for lb in r.get("labels", []) if lb != NEGATED_LABEL]
            negated = NEGATED_LABEL in r.get("labels", [])
            if not labels:
                warnings.append(f"{tid}: relation without a type label; skipped")
                continue
            head, tail = index[r["from_id"]], index[r["to_id"]]
            if r.get("direction") == "left":
                head, tail = tail, head
            for label in labels:
                relations.append(GoldRelation(head=head, tail=tail, type=label, negated=negated))
        out.append(
            GoldExample(
                id=tid,
                lang=lang or data.get("lang", "en"),
                text=text,
                entities=entities,
                relations=relations,
                source=source,
            )
        )
    return out, warnings


def load_export(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]
    return list(data)
