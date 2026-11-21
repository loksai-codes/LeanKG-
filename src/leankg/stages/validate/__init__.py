"""Validate stage(s). TODO: implemented in a later milestone; no-op placeholder for now."""

from typing import ClassVar

from leankg.stages.base import NoOpStage


class ValidateStage(NoOpStage):
    name: ClassVar[str] = "validate"


__all__ = ["ValidateStage"]
