"""Helpers shared by entity stages: creating mentions and resolving overlaps."""

from __future__ import annotations

from collections.abc import Iterable

from leankg.models import Document, Mention, Method, Sentence


def make_mention(
    doc: Document,
    sent: Sentence,
    start: int,
    end: int,
    type_: str,
    method: Method,
    confidence: float,
    *,
    normalized: str = "",
    ontology_id: str | None = None,
    pattern_id: str | None = None,
) -> Mention:
    return Mention(
        id=f"{sent.id}:m{start}-{end}:{method}",
        doc_id=doc.id,
        chunk_id=sent.chunk_id,
        sent_id=sent.id,
        start=start,
        end=end,
        text=sent.text[start:end],
        type=type_,
        method=method,
        lang=sent.lang,
        confidence=confidence,
        normalized=normalized,
        ontology_id=ontology_id,
        pattern_id=pattern_id,
    )


def longest_non_overlapping(spans: Iterable[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
    """Greedy longest-match: sort by (-length, start, payload) and keep non-overlapping.

    Each span is ``(start, end, payload)``. Deterministic for equal lengths (earliest wins).
    """
    chosen: list[tuple[int, int, int]] = []
    for s, e, p in sorted(spans, key=lambda x: (-(x[1] - x[0]), x[0], x[2])):
        if all(e <= cs or s >= ce for cs, ce, _ in chosen):
            chosen.append((s, e, p))
    return sorted(chosen)


def add_mentions(doc: Document, new: Iterable[Mention], *, keep_existing: bool = True) -> int:
    """Add mentions that don't overlap an existing one in the same sentence."""
    added = 0
    by_sent: dict[str, list[Mention]] = {}
    for m in doc.mentions:
        by_sent.setdefault(m.sent_id, []).append(m)
    for m in new:
        existing = by_sent.setdefault(m.sent_id, [])
        if keep_existing and any(m.overlaps(o) for o in existing):
            continue
        existing.append(m)
        doc.mentions.append(m)
        added += 1
    doc.mentions.sort(key=lambda m: (m.sent_id, m.start, m.end))
    return added
