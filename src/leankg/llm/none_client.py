"""NoneClient: LLM switched off. Hard cases are kept flagged, never sent anywhere."""

from __future__ import annotations

from leankg.llm.base import Usage
from leankg.models import HardCase, LLMVerdict


class NoneClient:
    name = "none"
    model = ""

    def __init__(self) -> None:
        self.usage = Usage()

    def classify(self, batch: list[HardCase]) -> list[LLMVerdict]:
        return []
