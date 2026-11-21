"""Preprocess stage(s). TODO: implemented in a later milestone; no-op placeholder for now."""

from typing import ClassVar

from leankg.stages.base import NoOpStage


class PreprocessStage(NoOpStage):
    name: ClassVar[str] = "preprocess"


__all__ = ["PreprocessStage"]
