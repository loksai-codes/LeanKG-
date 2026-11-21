"""OllamaClient: local LLM via Ollama's JSON-schema format mode (``[ollama]`` extra)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from leankg.config import LLMConfig
from leankg.llm.base import LLMError, Usage
from leankg.llm.prompt import build_messages
from leankg.llm.schema import verdict_schema
from leankg.llm.validate import match_verdicts, parse_response
from leankg.models import HardCase, LLMVerdict


class OllamaClient:
    name = "ollama"

    def __init__(
        self, cfg: LLMConfig, client: Any = None, hints: Mapping[str, str] | None = None
    ) -> None:
        if not cfg.model:
            raise LLMError(
                "no Ollama model configured: set [llm].model (e.g. a local qwen/llama tag)"
            )
        self.cfg = cfg
        self.model = cfg.model
        self.hints: Mapping[str, str] = hints or {}
        self.usage = Usage()
        if client is None:
            try:
                import ollama
            except ImportError as exc:  # pragma: no cover - depends on extras
                raise LLMError("the Ollama client needs: pip install 'leankg[ollama]'") from exc
            client = ollama.Client(host=cfg.ollama_host)
        self._client = client

    @classmethod
    def from_config(cls, cfg: LLMConfig) -> OllamaClient:
        return cls(cfg)

    def list_models(self) -> list[str]:
        resp = self._client.list()
        models = resp.get("models", []) if isinstance(resp, dict) else getattr(resp, "models", [])
        return sorted(
            str(m.get("model") if isinstance(m, dict) else getattr(m, "model", m)) for m in models
        )

    def classify(self, batch: list[HardCase]) -> list[LLMVerdict]:
        if not batch:
            return []
        resp = self._client.chat(
            model=self.model,
            messages=build_messages(batch, self.hints),
            format=verdict_schema(),
            options={"temperature": self.cfg.temperature},
        )
        get = resp.get if isinstance(resp, dict) else (lambda k, d=None: getattr(resp, k, d))
        message = get("message", {}) or {}
        content = (
            message.get("content", "")
            if isinstance(message, dict)
            else getattr(message, "content", "")
        )
        self.usage.add(int(get("prompt_eval_count", 0) or 0), int(get("eval_count", 0) or 0))
        verdicts = match_verdicts(batch, parse_response(str(content or "")))
        return [verdicts[c.case_id] for c in batch if c.case_id in verdicts]
