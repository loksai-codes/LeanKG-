"""Linking stage: exact/synonym → RapidFuzz → multilingual embeddings (optional).

Every mention gets an ``entity_id``. Linked mentions use the ontology concept id (shared by
all languages, so a Japanese mention and an English mention of the same concept become one
entity); unlinked ones get ``<pack>:<Type>:<normalized surface>``.
"""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from leankg.domain.pack import Concept, DomainPack
from leankg.models import Alias, Document, Entity, LinkCandidate, Mention, Provenance
from leankg.stages.base import BaseStage, StageContext

log = logging.getLogger(__name__)


class _LangIndex:
    """All concept surfaces (every language) normalized with one language's profile."""

    def __init__(self, pack: DomainPack, profile: Any) -> None:
        self.exact: dict[str, list[str]] = {}
        self.keys: list[str] = []
        self.key_ids: list[str] = []
        for concept in pack.concepts.values():
            for _lang, surface in concept.all_surfaces():
                key = profile.normalize(surface)
                if not key:
                    continue
                ids = self.exact.setdefault(key, [])
                if concept.id not in ids:
                    ids.append(concept.id)
                    self.keys.append(key)
                    self.key_ids.append(concept.id)


class LinkingStage(BaseStage):
    name: ClassVar[str] = "linking"

    def __init__(self, ctx: StageContext) -> None:
        super().__init__(ctx)
        self._indexes: dict[str, _LangIndex] = {}
        self._embedder: Any = None
        self._embedder_failed = False

    # ---------------------------------------------------------------- indexes
    def _index(self, lang: str) -> _LangIndex:
        if lang not in self._indexes:
            self._indexes[lang] = _LangIndex(
                self.ctx.require_pack(), self.ctx.get_profiles().get(lang)
            )
        return self._indexes[lang]

    def embedder(self) -> Any:
        """Lazy multilingual embedding linker (``[embed]`` extra), or ``None``."""
        if self._embedder is None and not self._embedder_failed:
            cfg = self.config.linking
            pack = self.ctx.require_pack()
            model = pack.models.embeddings.get("model", "")
            if not cfg.use_embeddings or not model:
                self._embedder_failed = True
                return None
            try:
                from leankg.stages.linking.embed import EmbeddingLinker

                self._embedder = EmbeddingLinker(pack, model, cache_dir=cfg.cache_dir)
            except ImportError:
                log.info("sentence-transformers not installed; embedding linking off")
                self._embedder_failed = True
        return self._embedder

    # ---------------------------------------------------------------- linking
    def _fuzzy(self, mention: Mention, idx: _LangIndex, profile: Any) -> list[LinkCandidate]:
        from rapidfuzz import fuzz, process

        scorer = (
            fuzz.WRatio if getattr(profile, "fuzzy_scorer", "wratio") == "wratio" else fuzz.ratio
        )
        pack = self.ctx.require_pack()
        results = process.extract(
            mention.normalized, idx.keys, scorer=scorer, limit=8,
            score_cutoff=self.config.linking.fuzzy_threshold,
        )  # fmt: skip
        best: dict[str, float] = {}
        for _key, score, pos in results:
            cid = idx.key_ids[pos]
            concept = pack.concepts[cid]
            if concept.type != mention.type:
                continue
            if score > best.get(cid, 0):
                best[cid] = float(score)
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
        return [
            LinkCandidate(entity_id=cid, ontology_id=cid, score=s / 100, method="fuzzy")
            for cid, s in ranked
        ]

    def link(self, mention: Mention) -> None:
        pack = self.ctx.require_pack()
        profile = self.ctx.get_profiles().get(mention.lang)
        if not mention.normalized:
            mention.normalized = profile.normalize(mention.text)
        if mention.ontology_id and mention.ontology_id in pack.concepts:
            mention.link_method = "dict"
            mention.link_score = 1.0
            if len({c.ontology_id for c in mention.candidates}) > 1:
                mention.ambiguous = True
        else:
            idx = self._index(mention.lang)
            ids = idx.exact.get(mention.normalized, [])
            typed = [i for i in ids if pack.concepts[i].type == mention.type] or ids
            if typed:
                mention.ontology_id = typed[0]
                mention.link_method = "exact"
                mention.link_score = 1.0
                mention.type = pack.concepts[typed[0]].type
                mention.ambiguous = len(typed) > 1
                mention.candidates = [
                    LinkCandidate(entity_id=i, ontology_id=i, score=1.0, method="exact")
                    for i in typed
                ]
            else:
                cands = self._fuzzy(mention, idx, profile)
                margin = self.config.linking.fuzzy_margin / 100
                emb = self.embedder() if not cands else None
                if emb is not None:
                    cands = emb.candidates(mention, self.config.linking.embed_threshold)
                    margin = self.config.linking.embed_margin
                if cands:
                    top = cands[0]
                    mention.ontology_id = top.ontology_id
                    mention.link_method = top.method
                    mention.link_score = top.score
                    mention.candidates = cands[:3]
                    mention.ambiguous = len(cands) > 1 and cands[0].score - cands[1].score <= margin
        mention.entity_id = (
            mention.ontology_id
            if mention.ontology_id
            else f"{pack.name}:{mention.type}:{mention.normalized}"
        )
        for c in mention.candidates:
            if not c.entity_id and c.ontology_id:
                c.entity_id = c.ontology_id

    def process(self, doc: Document) -> Document:
        for m in doc.mentions:
            self.link(m)
        doc.entities = build_entities(doc, self.ctx.require_pack())
        return doc


def _names(concept: Concept | None, mentions: list[Mention]) -> tuple[str, str | None]:
    if concept is not None:
        name = concept.preferred("en") or next(iter(concept.names.values()))[0]
        return name, concept.preferred("ja")
    first = mentions[0]
    return first.text, None


def build_entities(doc: Document, pack: DomainPack) -> list[Entity]:
    """Group a document's linked mentions into entities."""
    groups: dict[str, list[Mention]] = {}
    for m in doc.mentions:
        if m.entity_id:
            groups.setdefault(m.entity_id, []).append(m)
    sentences = doc.sentence_index()
    entities = []
    for eid, ms in groups.items():
        concept = pack.concepts.get(ms[0].ontology_id or "")
        name, name_ja = _names(concept, ms)
        aliases: dict[tuple[str, str], None] = {}
        if concept is not None:
            for lang, surface in concept.all_surfaces():
                aliases[(surface, lang)] = None
        for m in ms:
            aliases[(m.text, m.lang)] = None
        provenance = []
        for m in ms:
            sent = sentences.get(m.sent_id)
            offset = sent.start if sent is not None else 0
            provenance.append(
                Provenance(
                    doc_id=m.doc_id,
                    chunk_id=m.chunk_id,
                    sent_id=m.sent_id,
                    start=offset + m.start,
                    end=offset + m.end,
                    method=m.method,
                    lang=m.lang,
                    confidence=m.confidence,
                    pattern_id=m.pattern_id,
                )
            )
        entities.append(
            Entity(
                id=eid,
                type=concept.type if concept is not None else ms[0].type,
                name=name,
                name_ja=name_ja,
                aliases=[Alias(text=t, lang=lg) for t, lg in aliases],
                ontology_id=concept.id if concept is not None else None,
                domain=pack.name,
                lang_seen=sorted({m.lang for m in ms}),
                mention_count=len(ms),
                confidence=max(m.confidence for m in ms),
                provenance=provenance,
            )
        )
    return entities


from leankg.stages.linking.chunk_embed import ChunkEmbedStage  # noqa: E402

__all__ = ["ChunkEmbedStage", "LinkingStage", "build_entities"]
