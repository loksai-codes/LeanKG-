"""GroqClient. TODO: implemented in M4."""

from __future__ import annotations

from leankg.config import LLMConfig
from leankg.llm.base import LLMError


class GroqClient:
    @classmethod
    def from_config(cls, cfg: LLMConfig) -> GroqClient:
        raise LLMError("GroqClient is not implemented yet (M4)")
