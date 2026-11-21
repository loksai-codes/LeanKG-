"""Language-neutral prompt for hard cases (docs/GROQ.md "Prompt").

The LLM never sees whole documents. Per case it gets the sentence (EN or JA), the entities
already found as ``[i] surface (Type)``, and the allowed relation types per ordered pair.
It answers with indices and relation names only, so the answer has the same shape for
every language. Bump ``PROMPT_VERSION`` whenever the wording changes (it is part of the
cache key).
"""

from __future__ import annotations

from collections.abc import Mapping

from leankg.models import HardCase

PROMPT_VERSION = "2026-11-21.1"

SYSTEM_PROMPT = """\
You are a careful information-extraction referee for a knowledge graph.
For each case you get one sentence (English or Japanese), a numbered list of entities that
were already found in it, and the relation types allowed for each ordered entity pair.

Return only relations that the sentence itself states (not world knowledge):
- "head" and "tail" are entity indices from the list; use only the listed pairs and types.
- "negated": true when the sentence denies the relation (e.g. "did not reduce", 〜しなかった,
  〜ではない). A negated relation is still reported, with negated=true.
- "hedged": true when the sentence is speculative (may, might, 可能性がある, かもしれない).
- "confidence": your probability (0 to 1) that the relation is stated as given.
- If no allowed relation is stated, return an empty "relations" list for that case.
- "link_choice": when a case has a link question, the index of the option the mention
  refers to; otherwise null.
Answer with JSON matching the schema: {"verdicts": [{"case_id", "relations", "link_choice"}]}
with exactly one verdict per case, in the same order as the cases."""


def render_case(case: HardCase) -> str:
    lines = [f"Case {case.case_id} (lang={case.lang})", f"Sentence: {case.sentence}", "Entities:"]
    lines += [f"[{e.index}] {e.surface} ({e.type})" for e in case.entities]
    lines.append("Allowed relations (head -> tail):")
    if case.allowed:
        lines += [f"[{a.head}] -> [{a.tail}]: {', '.join(a.types)}" for a in case.allowed]
    else:
        lines.append("(none)")
    if case.link_question is not None:
        q = case.link_question
        opts = "; ".join(f"{i}: {o}" for i, o in enumerate(q.options))
        lines.append(f"Link question: which concept does entity [{q.entity}] refer to? {opts}")
    return "\n".join(lines)


def build_messages(
    batch: list[HardCase], hints: Mapping[str, str] | None = None
) -> list[dict[str, str]]:
    """Chat messages for one batch. Few-shot examples come from the pack's
    ``llm_hints.md`` (+ ``llm_hints.<lang>.md`` for each language present in the batch)."""
    hints = hints or {}
    langs = sorted({c.lang for c in batch})
    parts: list[str] = []
    examples = [
        hints[lang].strip() for lang in ["en", *[x for x in langs if x != "en"]] if hints.get(lang)
    ]
    if examples:
        parts.append("Worked examples:\n\n" + "\n\n".join(examples))
    parts.append("Cases:\n\n" + "\n\n".join(render_case(c) for c in batch))
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
