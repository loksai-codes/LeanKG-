"""Local validation of LLM answers (strict decoding is not a substitute for checking)."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from leankg.llm.schema import LLMBatchResponse
from leankg.models import HardCase, LLMRelation, LLMVerdict


def parse_response(text: str) -> list[LLMVerdict]:
    """Parse the model's JSON text into verdicts (Pydantic-validated)."""
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            return []
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return []
    try:
        return LLMBatchResponse.model_validate(data).verdicts
    except ValidationError:
        # salvage verdicts one by one
        out = []
        for item in data.get("verdicts", []) if isinstance(data, dict) else []:
            try:
                out.append(LLMVerdict.model_validate(item))
            except ValidationError:
                continue
        return out


def check_verdict(case: HardCase, verdict: LLMVerdict) -> tuple[LLMVerdict, list[str]]:
    """Drop relations with unknown indices / disallowed types; returns (clean, problems)."""
    allowed = {(a.head, a.tail): set(a.types) for a in case.allowed}
    n = len(case.entities)
    keep: list[LLMRelation] = []
    problems: list[str] = []
    for r in verdict.relations:
        if not (0 <= r.head < n and 0 <= r.tail < n):
            problems.append(f"{case.case_id}: index out of range {r.head}->{r.tail}")
            continue
        if r.type not in allowed.get((r.head, r.tail), set()):
            problems.append(f"{case.case_id}: {r.type} not allowed for [{r.head}]->[{r.tail}]")
            continue
        if any((k.head, k.tail, k.type) == (r.head, r.tail, r.type) for k in keep):
            continue
        keep.append(r)
    link = verdict.link_choice
    if link is not None:
        q = case.link_question
        if q is None or not (0 <= link < len(q.options)):
            problems.append(f"{case.case_id}: invalid link_choice {link}")
            link = None
    return LLMVerdict(case_id=case.case_id, relations=keep, link_choice=link), problems


def match_verdicts(batch: list[HardCase], verdicts: list[LLMVerdict]) -> dict[str, LLMVerdict]:
    """Map verdicts to cases by case_id (falling back to order), validating each."""
    by_id = {v.case_id: v for v in verdicts}
    out: dict[str, LLMVerdict] = {}
    for i, case in enumerate(batch):
        v = by_id.get(case.case_id)
        if v is None and len(verdicts) == len(batch):
            v = verdicts[i]
        if v is None:
            continue
        out[case.case_id], _ = check_verdict(case, v)
    return out
