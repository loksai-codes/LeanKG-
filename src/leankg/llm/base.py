"""LLM client interface. The LLM only ever answers hard cases with indices + relation names."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from leankg.models import HardCase, LLMVerdict


@dataclass
class Usage:
    """Accumulated usage of one client (real token counts from responses)."""

    requests: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    retries: int = 0
    escalations: int = 0

    def add(self, tokens_in: int, tokens_out: int) -> None:
        self.requests += 1
        self.tokens_in += tokens_in
        self.tokens_out += tokens_out


class LLMError(RuntimeError):
    """Raised for configuration problems or unrecoverable provider errors."""


@runtime_checkable
class LLMClient(Protocol):
    name: str
    model: str
    usage: Usage

    def classify(self, batch: list[HardCase]) -> list[LLMVerdict]: ...
