"""``leankg review-llm``: turn recurring LLM answers into cheap rules.

Reads the JSONL log written by the resolver, groups confirmed relations by
``(language, relation, trigger phrase)`` — the words between the arguments for English,
the predicate after them (≈ bunsetsu head) for Japanese, chosen by the language profile —
and suggests trigger entries that aren't in the pack yet. Link choices made by the LLM
become synonym suggestions. ``apply`` writes them to ``patterns/relations.<lang>.learned.yaml``
and ``dictionaries/learned_<lang>.csv`` (both picked up by the pack loader).
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from leankg.domain.pack import DomainPack
from leankg.lang.base import ProfileRegistry
from leankg.models import HardCase, LLMVerdict


@dataclass
class TriggerSuggestion:
    lang: str
    relation: str
    phrase: str
    position: str
    order: str
    count: int
    examples: list[str] = field(default_factory=list)


@dataclass
class SynonymSuggestion:
    lang: str
    surface: str
    concept_id: str
    type: str
    count: int


def load_log(path: str | Path) -> list[tuple[HardCase, LLMVerdict]]:
    p = Path(path)
    if not p.is_file():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row: dict[str, Any] = json.loads(line)
        out.append(
            (HardCase.model_validate(row["case"]), LLMVerdict.model_validate(row["verdict"]))
        )
    return out


def _span(sentence: str, surface: str) -> tuple[int, int] | None:
    i = sentence.find(surface)
    return (i, i + len(surface)) if i >= 0 else None


def _known(pack: DomainPack, lang: str, profiles: ProfileRegistry) -> set[tuple[str, str]]:
    profile = profiles.get(lang)
    return {
        (choice.type, profile.normalize(w))
        for rule in pack.relations_for(lang).triggers
        for choice in rule.relations
        for w in rule.words
    }


def suggest(
    entries: list[tuple[HardCase, LLMVerdict]],
    pack: DomainPack,
    min_count: int = 2,
    profiles: ProfileRegistry | None = None,
) -> tuple[list[TriggerSuggestion], list[SynonymSuggestion]]:
    profiles = profiles or ProfileRegistry()
    groups: dict[tuple[str, str, str, str, str], list[str]] = defaultdict(list)
    synonyms: dict[tuple[str, str, str, str], int] = defaultdict(int)
    for case, verdict in entries:
        profile = profiles.get(case.lang)
        for r in verdict.relations:
            if r.negated:
                continue
            head, tail = case.entities[r.head], case.entities[r.tail]
            hs, ts = _span(case.sentence, head.surface), _span(case.sentence, tail.surface)
            if hs is None or ts is None:
                continue
            first, second, order = (hs, ts, "forward") if hs[0] < ts[0] else (ts, hs, "reverse")
            found = profile.trigger_phrase(case.sentence, first, second)
            if found is None:
                continue
            phrase, position = found
            groups[(case.lang, r.type, phrase, position, order)].append(case.sentence)
        q = case.link_question
        if q is not None and verdict.link_choice is not None:
            ent = case.entities[q.entity]
            cid = q.option_ids[verdict.link_choice]
            concept = pack.concepts.get(cid)
            if concept is not None:
                synonyms[(case.lang, ent.surface, cid, concept.type)] += 1
    triggers = []
    known: dict[str, set[tuple[str, str]]] = {}
    for (lang, rel, phrase, position, order), sents in groups.items():
        if len(sents) < min_count:
            continue
        known.setdefault(lang, _known(pack, lang, profiles))
        if (rel, profiles.get(lang).normalize(phrase)) in known[lang]:
            continue
        triggers.append(
            TriggerSuggestion(lang, rel, phrase, position, order, len(sents), sents[:3])
        )
    triggers.sort(key=lambda s: (-s.count, s.lang, s.relation, s.phrase))
    syns = [
        SynonymSuggestion(lang, surface, cid, type_, n)
        for (lang, surface, cid, type_), n in synonyms.items()
        if n >= min_count
    ]
    syns.sort(key=lambda s: (-s.count, s.surface))
    return triggers, syns


def apply(
    pack: DomainPack, triggers: list[TriggerSuggestion], synonyms: list[SynonymSuggestion]
) -> list[Path]:
    if pack.root is None:
        raise ValueError("pack has no root folder")
    written: list[Path] = []
    by_lang: dict[str, list[TriggerSuggestion]] = defaultdict(list)
    for trig in triggers:
        by_lang[trig.lang].append(trig)
    for lang, items in by_lang.items():
        path = pack.root / "patterns" / f"relations.{lang}.learned.yaml"
        data: dict[str, Any] = {"triggers": []}
        if path.is_file():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {"triggers": []}
        existing = {r["id"] for r in data.get("triggers", [])}
        for t in items:
            rid = f"learned-{t.relation.lower()}-{t.position}-{t.order}-{len(existing)}"
            existing.add(rid)
            data.setdefault("triggers", []).append(
                {"id": rid, "relations": [{"type": t.relation}], "words": [t.phrase],
                 "position": t.position, "order": t.order, "window": 6, "weight": 0.9}
            )  # fmt: skip
        header = "# Written by `leankg review-llm --apply` from logged LLM answers. Review me.\n"
        path.write_text(
            header + yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
        )
        written.append(path)
    syn_by_lang: dict[str, list[SynonymSuggestion]] = defaultdict(list)
    for syn in synonyms:
        syn_by_lang[syn.lang].append(syn)
    for lang, syn_items in syn_by_lang.items():
        path = pack.root / "dictionaries" / f"learned_{lang}.csv"
        new_file = not path.is_file()
        with path.open("a", encoding="utf-8", newline="") as fh:
            w = csv.writer(fh)
            if new_file:
                w.writerow(["id", "type", "lang", "term", "synonyms", "source"])
            for syn_item in syn_items:
                w.writerow(
                    [syn_item.concept_id, syn_item.type, lang, syn_item.surface, "", "review-llm"]
                )
        written.append(path)
    return written
