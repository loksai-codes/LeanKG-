"""Core data models shared by every pipeline stage.

All offsets are character offsets. ``Sentence.start/end`` are relative to the chunk text,
``Chunk.start/end`` relative to the document text, and ``Mention.start/end`` relative to
the sentence text. ``Provenance.start/end`` are relative to the chunk text.
"""

from __future__ import annotations

from collections.abc import Iterator
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, computed_field

Method = Literal["dict", "regex", "ner", "gliner", "dep", "trigger", "cooc", "llm"]
METHODS: tuple[str, ...] = ("dict", "regex", "ner", "gliner", "dep", "trigger", "cooc", "llm")
RULE_METHODS: frozenset[str] = frozenset({"dep", "trigger"})

TripleStatus = Literal["accepted", "candidate", "unverified", "negative", "rejected"]
LinkMethod = Literal["dict", "exact", "fuzzy", "embed", "llm", "none"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=False)


class Provenance(_Model):
    """Where a node or edge came from."""

    doc_id: str
    chunk_id: str
    sent_id: str
    start: int
    end: int
    method: Method
    lang: str
    confidence: float
    pattern_id: str | None = None


class Sentence(_Model):
    id: str
    doc_id: str
    chunk_id: str
    index: int
    start: int
    end: int
    text: str
    lang: str
    _spacy: Any = PrivateAttr(default=None)

    @property
    def spacy_doc(self) -> Any:
        """The spaCy ``Doc`` for this sentence, set by the preprocess stage."""
        return self._spacy

    def set_spacy_doc(self, doc: Any) -> None:
        self._spacy = doc


class Chunk(_Model):
    id: str
    doc_id: str
    index: int
    start: int
    end: int
    text: str
    lang: str
    sentences: list[Sentence] = Field(default_factory=list)
    embedding: list[float] | None = None


class LinkCandidate(_Model):
    entity_id: str
    ontology_id: str | None
    score: float
    method: LinkMethod


class Mention(_Model):
    id: str
    doc_id: str
    chunk_id: str
    sent_id: str
    start: int
    end: int
    text: str
    type: str
    method: Method
    lang: str
    confidence: float
    normalized: str = ""
    pattern_id: str | None = None
    ontology_id: str | None = None
    entity_id: str | None = None
    link_method: LinkMethod = "none"
    link_score: float = 0.0
    ambiguous: bool = False
    candidates: list[LinkCandidate] = Field(default_factory=list)

    def overlaps(self, other: Mention) -> bool:
        return self.sent_id == other.sent_id and self.start < other.end and other.start < self.end


class Alias(_Model):
    text: str
    lang: str


class Entity(_Model):
    id: str
    type: str
    name: str
    name_ja: str | None = None
    aliases: list[Alias] = Field(default_factory=list)
    ontology_id: str | None = None
    domain: str = ""
    lang_seen: list[str] = Field(default_factory=list)
    mention_count: int = 0
    confidence: float = 0.0
    provenance: list[Provenance] = Field(default_factory=list)

    def aliases_for(self, lang: str) -> list[str]:
        return sorted({a.text for a in self.aliases if a.lang == lang})


class RelationCandidate(_Model):
    """A possible relation for a pair; ``reverse`` swaps head and tail."""

    type: str
    reverse: bool = False


class Triple(_Model):
    id: str
    head_mention: str
    tail_mention: str
    head: str = ""
    tail: str = ""
    type: str = ""
    candidates: list[RelationCandidate] = Field(default_factory=list)
    method: Method
    confidence: float = 0.0
    negated: bool = False
    hedged: bool = False
    complex: bool = False
    allow_flip: bool = False
    status: TripleStatus = "candidate"
    pattern_id: str | None = None
    weight: float = 1.0
    doc_id: str = ""
    sent_id: str = ""
    evidence_count: int = 1
    chunk_ids: list[str] = Field(default_factory=list)
    doc_ids: list[str] = Field(default_factory=list)
    langs: list[str] = Field(default_factory=list)
    provenance: list[Provenance] = Field(default_factory=list)

    @property
    def key(self) -> tuple[str, str, str, bool]:
        return (self.head, self.tail, self.type, self.negated)


class HardCaseReason(StrEnum):
    NO_RULE_RELATION = "no_rule_relation"
    AMBIGUOUS_LINK = "ambiguous_link"
    LOW_CONFIDENCE = "low_confidence"
    COMPLEX_NEGATION = "complex_negation"
    ROUTE_ALL = "route_all"


class HardCaseEntity(_Model):
    index: int
    surface: str
    type: str
    mention_id: str


class AllowedRelation(_Model):
    head: int
    tail: int
    types: list[str]


class LinkQuestion(_Model):
    entity: int
    options: list[str]
    option_ids: list[str]


class HardCase(_Model):
    case_id: str
    doc_id: str
    sent_id: str
    lang: str
    sentence: str
    entities: list[HardCaseEntity]
    allowed: list[AllowedRelation]
    reasons: list[HardCaseReason]
    link_question: LinkQuestion | None = None


class LLMRelation(_Model):
    head: int
    tail: int
    type: str
    negated: bool = False
    hedged: bool = False
    confidence: float = Field(ge=0.0, le=1.0)


class LLMVerdict(_Model):
    case_id: str
    relations: list[LLMRelation] = Field(default_factory=list)
    link_choice: int | None = None


class Document(_Model):
    id: str
    source: str = ""
    title: str = ""
    url: str | None = None
    date: str | None = None
    lang: str = "en"
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    chunks: list[Chunk] = Field(default_factory=list)
    mentions: list[Mention] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    triples: list[Triple] = Field(default_factory=list)
    hard_cases: list[HardCase] = Field(default_factory=list)
    stage_log: list[str] = Field(default_factory=list)

    def sentences(self) -> Iterator[Sentence]:
        for chunk in self.chunks:
            yield from chunk.sentences

    def sentence_index(self) -> dict[str, Sentence]:
        return {s.id: s for s in self.sentences()}

    def chunk_index(self) -> dict[str, Chunk]:
        return {c.id: c for c in self.chunks}

    def mention_index(self) -> dict[str, Mention]:
        return {m.id: m for m in self.mentions}

    def mentions_in(self, sent_id: str) -> list[Mention]:
        return sorted(
            (m for m in self.mentions if m.sent_id == sent_id), key=lambda m: (m.start, m.end)
        )


class LangStats(BaseModel):
    """Counters for one language (or the overall run)."""

    docs: int = 0
    chunks: int = 0
    sentences: int = 0
    mentions: int = 0
    entities: int = 0
    triples: int = 0
    triples_negative: int = 0
    triples_unverified: int = 0
    hard_case_sentences: int = 0
    llm_sentences: int = 0
    llm_requests: int = 0
    cache_hits: int = 0
    dedupe_hits: int = 0
    budget_skipped: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    est_cost_usd: float = 0.0
    f1: float | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def llm_call_rate(self) -> float:
        """Share of sentences handed to the LLM layer (cache hits included)."""
        return self.llm_sentences / self.sentences if self.sentences else 0.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def hard_case_rate(self) -> float:
        """Share of sentences the router flagged as hard (sent or not)."""
        return self.hard_case_sentences / self.sentences if self.sentences else 0.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cache_hit_rate(self) -> float:
        """Share of LLM-layer sentences answered from cache or in-run dedupe."""
        hits = self.cache_hits + self.dedupe_hits
        return hits / self.llm_sentences if self.llm_sentences else 0.0


class RunReport(LangStats):
    """Summary printed at the end of every build."""

    domain: str = ""
    provider: str = "none"
    model: str = ""
    stages: list[str] = Field(default_factory=list)
    skipped_stages: list[str] = Field(default_factory=list)
    duration_s: float = 0.0
    budget_exhausted: bool = False
    by_lang: dict[str, LangStats] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def docs_per_min(self) -> float:
        return self.docs / self.duration_s * 60 if self.duration_s > 0 else 0.0

    @computed_field  # type: ignore[prop-decorator]
    @property
    def cost_per_1k_docs_usd(self) -> float:
        return self.est_cost_usd / self.docs * 1000 if self.docs else 0.0

    def lang(self, code: str) -> LangStats:
        return self.by_lang.setdefault(code, LangStats())
