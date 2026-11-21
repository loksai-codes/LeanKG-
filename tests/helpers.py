"""Test helpers: tiny pipelines over a pack without touching the network or Neo4j."""

from __future__ import annotations

from collections.abc import Sequence

from leankg.config import Config
from leankg.domain.loader import load_pack
from leankg.graph import KnowledgeGraph
from leankg.lang.base import ProfileRegistry
from leankg.llm.none_client import NoneClient
from leankg.models import Document
from leankg.pipeline import Pipeline
from leankg.stages.base import StageContext

_PACKS: dict[str, object] = {}
_PROFILES = ProfileRegistry()


def make_ctx(domain: str = "health_stress", config: Config | None = None) -> StageContext:
    if domain not in _PACKS:
        _PACKS[domain] = load_pack(domain)
    pack = _PACKS[domain]
    return StageContext(
        config=config or Config(),
        pack=pack,  # type: ignore[arg-type]
        profiles=_PROFILES,
        llm=NoneClient(),
        graph=KnowledgeGraph(domain=domain),
    )


def run_stages(
    text: str,
    stages: Sequence[str],
    domain: str = "health_stress",
    config: Config | None = None,
    doc_id: str = "t",
) -> Document:
    ctx = make_ctx(domain, config)
    pipe = Pipeline(ctx=ctx, stage_names=list(stages))
    return pipe.run([Document(id=doc_id, text=text)])[0]


ENTITY_STAGES = ("ingest", "preprocess", "dictionary", "regex", "linking")


def mentions(text: str, domain: str = "health_stress") -> list[tuple[str, str, str]]:
    doc = run_stages(text, ENTITY_STAGES, domain)
    return [(m.text, m.type, m.method) for m in doc.mentions]
