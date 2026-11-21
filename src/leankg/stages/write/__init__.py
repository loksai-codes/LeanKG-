"""Write stage(s). TODO: implemented in a later milestone; no-op placeholder for now."""

from typing import ClassVar

from leankg.stages.base import NoOpStage


class WriteStage(NoOpStage):
    name: ClassVar[str] = "write"


__all__ = ["WriteStage"]
