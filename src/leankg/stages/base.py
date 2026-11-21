"""The stage interface every pipeline step implements: ``process(doc) -> doc``."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Protocol, runtime_checkable

from leankg.config import Config
from leankg.models import Document, RunReport

if TYPE_CHECKING:
    from leankg.domain.pack import DomainPack
    from leankg.lang.base import ProfileRegistry
    from leankg.llm.base import LLMClient


@runtime_checkable
class Stage(Protocol):
    """A pipeline stage. Stages are testable alone and can be skipped by config."""

    @property
    def name(self) -> str: ...

    def process(self, doc: Document) -> Document: ...


@dataclass
class StageContext:
    """Shared, read-mostly state handed to every stage."""

    config: Config
    pack: DomainPack | None = None
    llm: LLMClient | None = None
    report: RunReport = field(default_factory=RunReport)
    profiles: ProfileRegistry | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def get_profiles(self) -> ProfileRegistry:
        if self.profiles is None:
            from leankg.lang.base import ProfileRegistry

            self.profiles = ProfileRegistry()
        return self.profiles

    def require_pack(self) -> DomainPack:
        if self.pack is None:
            raise RuntimeError("this stage needs a domain pack (Pipeline.from_domain)")
        return self.pack


class BaseStage:
    """Convenience base class. Subclasses override :meth:`process`.

    ``process_many`` lets a stage see the whole corpus at once (used by the LLM stage to
    batch hard cases across documents); by default it maps :meth:`process`.
    """

    name: ClassVar[str] = "base"

    def __init__(self, ctx: StageContext) -> None:
        self.ctx = ctx

    @property
    def config(self) -> Config:
        return self.ctx.config

    def process(self, doc: Document) -> Document:
        return doc

    def process_many(self, docs: Iterable[Document]) -> list[Document]:
        return [self.process(d) for d in docs]


class NoOpStage(BaseStage):
    """Placeholder for a stage that is not built yet. Passes documents through."""

    name: ClassVar[str] = "noop"

    def process(self, doc: Document) -> Document:
        doc.stage_log.append(f"{self.name}:noop")
        return doc
