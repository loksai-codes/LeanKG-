"""FakeClient: canned verdicts for tests and offline demos — never a real model.

Responses are keyed by normalized sentence and name entities by *surface*, so fixtures
are easy to write::

    {"responses": [
      {"sentence": "摩耗は漏れの原因かもしれない。",
       "relations": [{"head": "漏れ", "tail": "摩耗", "type": "CAUSED_BY",
                      "negated": false, "hedged": true, "confidence": 0.8}],
       "link_choice": null}
    ]}

Unknown sentences get an empty verdict. Token usage is *estimated* (chars / 4) so the
cost-reporting path can be exercised; numbers from a FakeClient are not benchmarks.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from leankg.config import LLMConfig
from leankg.llm.base import Usage
from leankg.llm.cache import normalize_sentence
from leankg.llm.prompt import build_messages
from leankg.llm.validate import check_verdict
from leankg.models import HardCase, LLMRelation, LLMVerdict

Responder = Callable[[HardCase], LLMVerdict]


class FakeClient:
    name = "fake"

    def __init__(
        self,
        responses: list[dict[str, Any]] | None = None,
        responder: Responder | None = None,
        model: str = "fake-model",
    ) -> None:
        self.model = model
        self.usage = Usage()
        self.calls: list[list[HardCase]] = []
        self._responder = responder
        self._by_sentence = {normalize_sentence(r["sentence"]): r for r in (responses or [])}

    @classmethod
    def from_config(cls, cfg: LLMConfig) -> FakeClient:
        responses: list[dict[str, Any]] = []
        if cfg.fake_fixture:
            data = json.loads(Path(cfg.fake_fixture).read_text(encoding="utf-8"))
            responses = data.get("responses", []) if isinstance(data, dict) else data
        return cls(responses=responses, model=cfg.model or "fake-model")

    def _from_fixture(self, case: HardCase) -> LLMVerdict:
        entry = self._by_sentence.get(normalize_sentence(case.sentence))
        if entry is None:
            return LLMVerdict(case_id=case.case_id)
        index = {e.surface: e.index for e in case.entities}
        rels = []
        for r in entry.get("relations", []):
            if r["head"] in index and r["tail"] in index:
                rels.append(
                    LLMRelation(
                        head=index[r["head"]],
                        tail=index[r["tail"]],
                        type=r["type"],
                        negated=r.get("negated", False),
                        hedged=r.get("hedged", False),
                        confidence=r.get("confidence", 0.9),
                    )
                )
        return LLMVerdict(
            case_id=case.case_id, relations=rels, link_choice=entry.get("link_choice")
        )

    def classify(self, batch: list[HardCase]) -> list[LLMVerdict]:
        if not batch:
            return []
        self.calls.append(list(batch))
        messages = build_messages(batch)
        tokens_in = sum(len(m["content"]) for m in messages) // 4
        out = []
        for case in batch:
            verdict = self._responder(case) if self._responder else self._from_fixture(case)
            clean, _ = check_verdict(case, verdict)
            out.append(clean)
        self.usage.add(tokens_in, 40 * len(batch))
        return out
