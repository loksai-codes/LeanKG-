"""FakeClient. TODO: implemented in M4."""

from __future__ import annotations

from leankg.config import LLMConfig
from leankg.llm.base import LLMError


class FakeClient:
    @classmethod
    def from_config(cls, cfg: LLMConfig) -> FakeClient:
        raise LLMError("FakeClient is not implemented yet (M4)")
