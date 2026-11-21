"""GroqClient: hosted LLM fallback via the official ``groq`` SDK (``[groq]`` extra).

* Structured Outputs with ``strict: true`` and a schema generated from Pydantic.
* Every answer is validated locally (indices, allowed relation types).
* Model availability is checked once (``models.list()``) before the first request.
* HTTP 429: waits for ``retry-after`` (or ``x-ratelimit-reset-*``), otherwise exponential
  backoff with jitter; also retries connection errors and 5xx.
* Optional escalation model for cases whose answers fall below a confidence floor.

Model IDs, prices and limits come from config — never from code (docs/GROQ.md).
"""

from __future__ import annotations

import logging
import random
import re
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

from leankg.config import LLMConfig
from leankg.llm.base import LLMError, Usage
from leankg.llm.prompt import build_messages
from leankg.llm.schema import response_format
from leankg.llm.validate import match_verdicts, parse_response
from leankg.models import HardCase, LLMVerdict

log = logging.getLogger(__name__)

_DURATION = re.compile(
    r"(?:(\d+(?:\.\d+)?)h)?(?:(\d+(?:\.\d+)?)m(?!s))?(?:(\d+(?:\.\d+)?)s)?(?:(\d+)ms)?$"
)


def parse_reset(value: str | None) -> float | None:
    """Parse ``retry-after`` (seconds) or ``x-ratelimit-reset-*`` (``2m59.56s``, ``7.66s``)."""
    if not value:
        return None
    value = value.strip()
    try:
        return float(value)
    except ValueError:
        pass
    m = _DURATION.match(value)
    if not m or not any(m.groups()):
        return None
    h, mins, secs, ms = m.groups()
    return float(h or 0) * 3600 + float(mins or 0) * 60 + float(secs or 0) + float(ms or 0) / 1000


def _status(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    if code is None:
        resp = getattr(exc, "response", None)
        code = getattr(resp, "status_code", None)
    return int(code) if code is not None else None


def _headers(exc: BaseException) -> Mapping[str, str]:
    resp = getattr(exc, "response", None)
    headers = getattr(resp, "headers", None)
    return headers if headers is not None else {}


class GroqClient:
    name = "groq"

    def __init__(
        self,
        cfg: LLMConfig,
        client: Any = None,
        hints: Mapping[str, str] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not cfg.model:
            raise LLMError(
                "no Groq model configured: set [llm].model in leankg.toml or LEANKG_LLM_MODEL"
            )
        self.cfg = cfg
        self.model = cfg.model
        self.hints: Mapping[str, str] = hints or {}
        self.usage = Usage()
        self._sleep = sleep
        self._lock = threading.Lock()
        self._checked = False
        if client is None:
            key = cfg.api_key.get_secret_value() if cfg.api_key is not None else ""
            if not key:
                raise LLMError(
                    "GROQ_API_KEY is not set. Put it in .env (GROQ_API_KEY=...) or the environment."
                )
            try:
                from groq import Groq
            except ImportError as exc:  # pragma: no cover - depends on extras
                raise LLMError("the Groq client needs: pip install 'leankg[groq]'") from exc
            client = Groq(api_key=key, max_retries=0)
        self._client = client

    @classmethod
    def from_config(cls, cfg: LLMConfig) -> GroqClient:
        return cls(cfg)

    # ---------------------------------------------------------------- models
    def list_models(self) -> list[str]:
        resp = self._client.models.list()
        data = getattr(resp, "data", resp)
        return sorted(str(getattr(m, "id", m)) for m in data)

    def check_model(self) -> None:
        if self._checked or not self.cfg.verify_model:
            return
        served = self.list_models()
        for model in filter(None, [self.model, self.cfg.escalation_model]):
            if model not in served:
                raise LLMError(
                    f"Groq no longer serves model {model!r}. Run `leankg llm-models` to list "
                    "current models and update [llm].model in leankg.toml."
                )
        self._checked = True

    # --------------------------------------------------------------- request
    def _request(self, model: str, messages: list[dict[str, str]]) -> str:
        extra: dict[str, Any] = {}
        if self.cfg.reasoning_effort:
            extra["reasoning_effort"] = self.cfg.reasoning_effort
        if self.cfg.include_reasoning is not None:
            extra["include_reasoning"] = self.cfg.include_reasoning
        attempt = 0
        while True:
            try:
                resp = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=self.cfg.temperature,
                    max_completion_tokens=self.cfg.max_completion_tokens,
                    response_format=response_format(),
                    extra_body=extra or None,
                )
                break
            except Exception as exc:
                status = _status(exc)
                retryable = status in (408, 409, 429) or (status is not None and status >= 500)
                retryable = retryable or type(exc).__name__ in (
                    "APIConnectionError",
                    "APITimeoutError",
                )
                if not retryable or attempt >= self.cfg.max_retries:
                    raise LLMError(f"Groq request failed ({status}): {exc}") from exc
                headers = _headers(exc)
                wait = parse_reset(headers.get("retry-after"))
                if wait is None and status == 429:
                    wait = parse_reset(headers.get("x-ratelimit-reset-tokens")) or parse_reset(
                        headers.get("x-ratelimit-reset-requests")
                    )
                if wait is None:
                    wait = min(60.0, 2.0**attempt)
                wait += random.uniform(0, 0.25 * max(wait, 1.0))
                with self._lock:
                    self.usage.retries += 1
                log.info("Groq %s; retrying in %.1fs (attempt %d)", status, wait, attempt + 1)
                self._sleep(wait)
                attempt += 1
        usage = getattr(resp, "usage", None)
        with self._lock:
            self.usage.add(
                int(getattr(usage, "prompt_tokens", 0) or 0),
                int(getattr(usage, "completion_tokens", 0) or 0),
            )
        content = resp.choices[0].message.content
        return str(content or "")

    def _ask(self, model: str, batch: list[HardCase]) -> dict[str, LLMVerdict]:
        text = self._request(model, build_messages(batch, self.hints))
        return match_verdicts(batch, parse_response(text))

    # ----------------------------------------------------------------- public
    def classify(self, batch: list[HardCase]) -> list[LLMVerdict]:
        if not batch:
            return []
        self.check_model()
        verdicts = self._ask(self.model, batch)
        if self.cfg.escalation_model:
            unsure = [
                c for c in batch
                if c.case_id in verdicts
                and any(r.confidence < self.cfg.escalation_floor for r in verdicts[c.case_id].relations)
            ]  # fmt: skip
            if unsure:
                with self._lock:
                    self.usage.escalations += len(unsure)
                verdicts.update(self._ask(self.cfg.escalation_model, unsure))
        return [verdicts[c.case_id] for c in batch if c.case_id in verdicts]
