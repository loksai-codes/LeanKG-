"""Linking stage(s). TODO: implemented in a later milestone; no-op placeholder for now."""

from typing import ClassVar

from leankg.stages.base import NoOpStage


class LinkingStage(NoOpStage):
    name: ClassVar[str] = "linking"


__all__ = ["LinkingStage"]
