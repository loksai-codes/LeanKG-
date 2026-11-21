"""LLM clients (Groq, Ollama, none, fake) behind one ``classify(batch)`` interface."""

from __future__ import annotations

from typing import Any

from leankg.config import LLMConfig
from leankg.llm.base import LLMClient, LLMError, Usage
from leankg.llm.none_client import NoneClient


def make_client(cfg: LLMConfig) -> Any:
    """Create the configured client. Heavy SDKs are imported lazily."""
    if cfg.provider == "none":
        return NoneClient()
    if cfg.provider == "fake":
        from leankg.llm.fake_client import FakeClient

        return FakeClient.from_config(cfg)
    if cfg.provider == "groq":
        from leankg.llm.groq_client import GroqClient

        return GroqClient.from_config(cfg)
    if cfg.provider == "ollama":
        from leankg.llm.ollama_client import OllamaClient

        return OllamaClient.from_config(cfg)
    raise LLMError(f"unknown LLM provider {cfg.provider!r}")


__all__ = ["LLMClient", "LLMError", "NoneClient", "Usage", "make_client"]
