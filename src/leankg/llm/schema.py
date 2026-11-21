"""JSON schema for LLM answers, generated from Pydantic and made strict-mode compliant.

Groq Structured Outputs with ``strict: true`` require (docs/GROQ.md): every property listed
in ``required``, ``additionalProperties: false`` on every object, optional values as nullable
unions. Pydantic's schema is post-processed accordingly: ``$defs`` are inlined, titles and
defaults removed, ``anyOf [X, null]`` collapsed to ``{"type": [X, "null"]}`` and numeric
bounds dropped (they're enforced locally by Pydantic instead).
"""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel, Field

from leankg.models import LLMVerdict

SCHEMA_NAME = "verdicts"
_DROP_KEYS = {"title", "default", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
              "description", "examples"}  # fmt: skip


class LLMBatchResponse(BaseModel):
    verdicts: list[LLMVerdict] = Field(default_factory=list)


def _inline(node: Any, defs: dict[str, Any]) -> Any:
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return _inline(copy.deepcopy(defs[name]), defs)
        return {k: _inline(v, defs) for k, v in node.items() if k != "$defs"}
    if isinstance(node, list):
        return [_inline(v, defs) for v in node]
    return node


def _strictify(node: Any) -> Any:
    if isinstance(node, list):
        return [_strictify(v) for v in node]
    if not isinstance(node, dict):
        return node
    node = {k: _strictify(v) for k, v in node.items() if k not in _DROP_KEYS}
    any_of = node.get("anyOf")
    if isinstance(any_of, list) and len(any_of) == 2 and {"type": "null"} in any_of:
        other = next(v for v in any_of if v != {"type": "null"})
        if isinstance(other.get("type"), str) and set(other) <= {"type"}:
            node.pop("anyOf")
            node["type"] = [other["type"], "null"]
    if node.get("type") == "object" or "properties" in node:
        props = node.get("properties", {})
        node["type"] = "object"
        node["required"] = list(props)
        node["additionalProperties"] = False
    return node


def verdict_schema() -> dict[str, Any]:
    raw = LLMBatchResponse.model_json_schema()
    inlined = _inline(raw, raw.get("$defs", {}))
    strict: dict[str, Any] = _strictify(inlined)
    return strict


def response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {"name": SCHEMA_NAME, "strict": True, "schema": verdict_schema()},
    }


def strict_violations(schema: Any, path: str = "$") -> list[str]:
    """Walk a schema and list strict-mode rule violations (empty list = compliant)."""
    problems: list[str] = []
    if isinstance(schema, dict):
        if schema.get("type") == "object" or "properties" in schema:
            props = set(schema.get("properties", {}))
            if set(schema.get("required", [])) != props:
                problems.append(f"{path}: required != properties")
            if schema.get("additionalProperties") is not False:
                problems.append(f"{path}: additionalProperties must be false")
        if "$ref" in schema or "$defs" in schema:
            problems.append(f"{path}: unresolved $ref/$defs")
        for k, v in schema.items():
            problems.extend(strict_violations(v, f"{path}.{k}"))
    elif isinstance(schema, list):
        for i, v in enumerate(schema):
            problems.extend(strict_violations(v, f"{path}[{i}]"))
    return problems
