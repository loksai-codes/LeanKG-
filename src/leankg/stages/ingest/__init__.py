"""Ingest stage(s). TODO: implemented in a later milestone; no-op placeholder for now."""

from typing import ClassVar

from leankg.stages.base import NoOpStage


class IngestStage(NoOpStage):
    name: ClassVar[str] = "ingest"


__all__ = ["IngestStage"]
