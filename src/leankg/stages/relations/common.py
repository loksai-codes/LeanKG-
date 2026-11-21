"""Helpers shared by the relation stages."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from leankg.domain.pack import RelationChoice
from leankg.models import Document, Mention, Method, RelationCandidate, Sentence, Triple

METHOD_RANK: dict[str, int] = {"dep": 3, "trigger": 2, "llm": 2, "cooc": 1}


def mention_span(sdoc: Any, m: Mention) -> Any:
    """The token span covering a mention (expanded to token boundaries)."""
    return sdoc.char_span(m.start, m.end, alignment_mode="expand")


def token_mention(token: Any, mentions: list[Mention], use_subtree: bool = True) -> Mention | None:
    """Map a token to the mention it belongs to.

    1. a mention overlapping the token's characters;
    2. otherwise, if the token's subtree contains exactly one mention, that one
       (handles "the risk of X", "symptoms of X", "levels of X").
    """
    t_start, t_end = token.idx, token.idx + len(token.text)
    for m in mentions:
        if m.start < t_end and t_start < m.end:
            return m
    if not use_subtree:
        return None
    left, right = token.left_edge.idx, token.right_edge.idx + len(token.right_edge.text)
    inside = [m for m in mentions if m.start >= left and m.end <= right]
    return inside[0] if len(inside) == 1 else None


def with_conjuncts(token: Any) -> list[Any]:
    """The token plus its coordinated tokens (UD ``conj``): "X causes A and B"."""
    return [token, *list(token.conjuncts)]


def pairs(mentions: list[Mention]) -> Iterator[tuple[Mention, Mention]]:
    """Ordered pairs (a before b) of mentions of different entities."""
    for i, a in enumerate(mentions):
        for b in mentions[i + 1 :]:
            if a.entity_id and a.entity_id == b.entity_id:
                continue
            if a.overlaps(b):
                continue
            yield a, b


def related_pairs(doc: Document, sent_id: str) -> set[frozenset[str]]:
    """Mention-id pairs that already have a triple in this sentence."""
    return {
        frozenset((t.head_mention, t.tail_mention)) for t in doc.triples if t.sent_id == sent_id
    }


def to_candidates(choices: list[RelationChoice]) -> list[RelationCandidate]:
    return [RelationCandidate(type=c.type, reverse=c.reverse) for c in choices]


def new_triple(
    doc: Document,
    sent: Sentence,
    head: Mention,
    tail: Mention,
    method: Method,
    candidates: list[RelationCandidate],
    *,
    weight: float = 1.0,
    pattern_id: str | None = None,
    allow_flip: bool = False,
) -> Triple:
    return Triple(
        id=f"{sent.id}:{method}:{head.start}-{tail.start}:{pattern_id or ''}",
        head_mention=head.id,
        tail_mention=tail.id,
        candidates=candidates,
        method=method,
        weight=weight,
        pattern_id=pattern_id,
        allow_flip=allow_flip,
        doc_id=doc.id,
        sent_id=sent.id,
    )


def find_phrase(norm_text: str, phrase: str) -> Iterator[int]:
    """Start offsets of ``phrase`` in ``norm_text`` with ASCII word boundaries.

    Boundaries are only enforced on sides where the phrase starts/ends with an ASCII
    letter or digit, so "cause" doesn't match inside "because" while Japanese phrases
    (no spaces) match anywhere.
    """
    if not phrase:
        return
    start = 0
    n = len(phrase)
    while True:
        i = norm_text.find(phrase, start)
        if i < 0:
            return
        before = norm_text[i - 1] if i > 0 else " "
        after = norm_text[i + n] if i + n < len(norm_text) else " "
        ok_left = not (phrase[0].isascii() and phrase[0].isalnum()) or not before.isalnum()
        ok_right = not (phrase[-1].isascii() and phrase[-1].isalnum()) or not after.isalnum()
        if ok_left and ok_right:
            yield i
        start = i + 1
