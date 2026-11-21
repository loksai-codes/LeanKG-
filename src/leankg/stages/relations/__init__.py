"""Relations stage(s). TODO: implemented in a later milestone; no-op placeholder for now."""

from typing import ClassVar

from leankg.stages.base import NoOpStage


class DependencyStage(NoOpStage):
    name: ClassVar[str] = "dependency"


__all__ = ["DependencyStage"]
