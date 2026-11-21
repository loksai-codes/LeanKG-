"""OllamaClient. TODO: implemented in M4."""

from __future__ import annotations

from leankg.config import LLMConfig
from leankg.llm.base import LLMError


class OllamaClient:
    @classmethod
    def from_config(cls, cfg: LLMConfig) -> OllamaClient:
        raise LLMError("OllamaClient is not implemented yet (M4)")
