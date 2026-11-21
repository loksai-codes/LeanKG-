"""Domain pack models (validated with Pydantic).

A pack is pure data: ontology, dictionaries, patterns, model names and LLM hints. The
engine never hardcodes any of it.
"""

from __future__ import annotations

import re
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ANY_TYPE = "*"
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


# ------------------------------------------------------------------ ontology
class EntityTypeDef(_Strict):
    labels: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    parent: str | None = None


class RelationTypeDef(_Strict):
    from_: list[str] = Field(alias="from")
    to: list[str]
    labels: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    symmetric: bool = False


class Ontology(_Strict):
    version: int = 1
    name: str = ""
    description: str = ""
    entities: dict[str, EntityTypeDef]
    relations: dict[str, RelationTypeDef] = Field(default_factory=dict)

    @field_validator("entities", "relations")
    @classmethod
    def _identifiers(cls, value: dict[str, Any]) -> dict[str, Any]:
        for key in value:
            if not _IDENT.match(key):
                raise ValueError(
                    f"type name {key!r} must be an identifier ([A-Za-z_][A-Za-z0-9_]*)"
                )
        return value

    def check_references(self) -> list[str]:
        problems: list[str] = []
        for rel, rdef in self.relations.items():
            for side, types in (("from", rdef.from_), ("to", rdef.to)):
                for t in types:
                    if t != ANY_TYPE and t not in self.entities:
                        problems.append(f"relation {rel}: unknown entity type {t!r} in '{side}'")
        for name, edef in self.entities.items():
            if edef.parent and edef.parent not in self.entities:
                problems.append(f"entity {name}: unknown parent {edef.parent!r}")
        return problems


# -------------------------------------------------------------- dictionaries
class Term(_Strict):
    id: str
    type: str
    lang: str
    term: str
    synonyms: list[str] = Field(default_factory=list)
    source: str = ""
    file: str = ""
    line: int = 0

    def surfaces(self) -> list[str]:
        return [self.term, *self.synonyms]


class Concept(_Strict):
    """All dictionary rows that share an ``id``: one ontology concept, many surfaces."""

    id: str
    type: str
    names: dict[str, list[str]] = Field(default_factory=dict)

    def preferred(self, lang: str) -> str | None:
        names = self.names.get(lang)
        return names[0] if names else None

    def all_surfaces(self) -> list[tuple[str, str]]:
        return [(lang, s) for lang, names in self.names.items() for s in names]


# ------------------------------------------------------------------ patterns
class EntityPattern(_Strict):
    id: str
    type: str
    lang: str = ANY_TYPE
    pattern: str
    flags: str = ""
    group: int = 0
    confidence: float | None = None
    ontology_id: str | None = None

    @cached_property
    def regex(self) -> re.Pattern[str]:
        flags = 0
        for ch in self.flags:
            flags |= {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}[ch]
        return re.compile(self.pattern, flags)


class RelationChoice(_Strict):
    """A relation a pattern may produce; ``reverse`` swaps the matched head/tail."""

    type: str
    reverse: bool = False


class DepPattern(_Strict):
    """A spaCy DependencyMatcher pattern that yields a relation between two anchors."""

    id: str
    relations: list[RelationChoice]
    head: str = "head"
    tail: str = "tail"
    weight: float = 1.0
    pattern: list[dict[str, Any]]
    examples: list[str] = Field(default_factory=list)

    @field_validator("pattern")
    @classmethod
    def _no_yaml_booleans(cls, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        def walk(node: Any) -> None:
            if isinstance(node, bool):
                raise ValueError(
                    "pattern contains a boolean; YAML reads unquoted on/off/yes/no as "
                    'booleans, so quote them (e.g. "on")'
                )
            if isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)

        walk(value)
        names = [n.get("RIGHT_ID") for n in value]
        if not value or any(not isinstance(n, str) for n in names):
            raise ValueError("every pattern node needs a RIGHT_ID")
        return value


class TriggerRule(_Strict):
    """Trigger words for relations, with a window measured in profile units."""

    id: str
    relations: list[RelationChoice]
    words: list[str]

    @field_validator("words", mode="before")
    @classmethod
    def _words_are_strings(cls, value: Any) -> Any:
        if isinstance(value, list) and any(isinstance(w, bool) for w in value):
            raise ValueError("trigger words contain a boolean; quote on/off/yes/no in YAML")
        return value

    window: int = 6
    order: Literal["forward", "reverse"] = "forward"
    position: Literal["between", "after", "any"] = "between"
    weight: float = 1.0


class RelationPatterns(_Strict):
    lang: str = ""
    dependency: list[DepPattern] = Field(default_factory=list)
    triggers: list[TriggerRule] = Field(default_factory=list)
    negation_cues: list[str] = Field(default_factory=list)
    hedge_cues: list[str] = Field(default_factory=list)


# -------------------------------------------------------------------- models
class GlinerSettings(_Strict):
    model: str = ""
    label_lang: str = "en"
    labels: dict[str, dict[str, str]] = Field(default_factory=dict)
    threshold: float | None = None


class ModelsConfig(_Strict):
    spacy: dict[str, str] = Field(
        default_factory=lambda: {"en": "en_core_web_sm", "ja": "ja_ginza"}
    )
    extra_spacy: dict[str, list[str]] = Field(default_factory=dict)
    ner_label_map: dict[str, dict[str, str]] = Field(default_factory=dict)
    gliner: GlinerSettings = Field(default_factory=GlinerSettings)
    embeddings: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------- pack
class DomainPack(BaseModel):
    """A loaded, validated domain pack."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    root: Path | None = None
    ontology: Ontology
    terms: list[Term] = Field(default_factory=list)
    entity_patterns: list[EntityPattern] = Field(default_factory=list)
    relation_patterns: dict[str, RelationPatterns] = Field(default_factory=dict)
    models: ModelsConfig = Field(default_factory=ModelsConfig)
    llm_hints: dict[str, str] = Field(default_factory=dict)

    # -------------------------------------------------------------- lookups
    @property
    def entity_types(self) -> list[str]:
        return list(self.ontology.entities)

    @property
    def relation_types(self) -> list[str]:
        return list(self.ontology.relations)

    @cached_property
    def concepts(self) -> dict[str, Concept]:
        concepts: dict[str, Concept] = {}
        for t in self.terms:
            c = concepts.setdefault(t.id, Concept(id=t.id, type=t.type))
            names = c.names.setdefault(t.lang, [])
            for s in t.surfaces():
                if s not in names:
                    names.append(s)
        return concepts

    def terms_for(self, lang: str) -> list[Term]:
        return [t for t in self.terms if t.lang == lang]

    def patterns_for(self, lang: str) -> list[EntityPattern]:
        return [p for p in self.entity_patterns if p.lang in (lang, ANY_TYPE)]

    def relations_for(self, lang: str) -> RelationPatterns:
        return self.relation_patterns.get(lang, RelationPatterns(lang=lang))

    def type_matches(self, actual: str, allowed: list[str]) -> bool:
        if ANY_TYPE in allowed or actual in allowed:
            return True
        parent = self.ontology.entities.get(actual)
        while parent is not None and parent.parent:
            if parent.parent in allowed:
                return True
            parent = self.ontology.entities.get(parent.parent)
        return False

    def relation_allowed(self, rel: str, head_type: str, tail_type: str) -> bool:
        rdef = self.ontology.relations.get(rel)
        if rdef is None:
            return False
        if self.type_matches(head_type, rdef.from_) and self.type_matches(tail_type, rdef.to):
            return True
        return rdef.symmetric and (
            self.type_matches(tail_type, rdef.from_) and self.type_matches(head_type, rdef.to)
        )

    def allowed_relations(self, head_type: str, tail_type: str) -> list[str]:
        return [
            r for r in self.ontology.relations if self.relation_allowed(r, head_type, tail_type)
        ]

    def entity_label(self, type_name: str, lang: str) -> str:
        edef = self.ontology.entities.get(type_name)
        if edef is None:
            return type_name
        return edef.labels.get(lang) or edef.labels.get("en") or type_name
