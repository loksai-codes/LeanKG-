"""Text cleaning and sentence-aware, language-aware chunking."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from leankg.lang.detect import detect_language
from leankg.models import Chunk, Document, Sentence

_SPACES = re.compile(r"[ \t 　]+")
_MANY_NEWLINES = re.compile(r"\n{3,}")
_PARAGRAPHS = re.compile(r"\n\s*\n")


def clean_text(text: str) -> str:
    """Normalize newlines and runs of spaces; keep characters otherwise untouched.

    Ideographic spaces (U+3000) are folded to a normal space; matching keys are built later
    by the language profile, so no other normalization happens here.
    """
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    lines = [_SPACES.sub(" ", ln).strip() for ln in text.split("\n")]
    return _MANY_NEWLINES.sub("\n\n", "\n".join(lines)).strip()


@dataclass(frozen=True)
class _Piece:
    start: int
    end: int
    lang: str


SplitFn = Callable[[str, str], list[tuple[int, int]]]
"""``(text, lang) -> sentence spans``; provided by the language profiles."""


def paragraphs(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    prev = 0
    for m in _PARAGRAPHS.finditer(text):
        if m.start() > prev:
            spans.append((prev, m.start()))
        prev = m.end()
    if prev < len(text):
        spans.append((prev, len(text)))
    return spans


def chunk_document(
    doc: Document,
    split: SplitFn,
    target_for: Callable[[str], int],
    threshold: float = 0.2,
) -> list[Chunk]:
    """Split ``doc.text`` into chunks of whole sentences.

    Language is detected per paragraph; a chunk never mixes languages and stops growing
    once adding the next sentence would exceed the language's target size.
    """
    text = doc.text
    pieces: list[_Piece] = []
    for p_start, p_end in paragraphs(text):
        para = text[p_start:p_end]
        lang = detect_language(para, threshold, default=doc.lang)
        for s_start, s_end in split(para, lang):
            pieces.append(_Piece(p_start + s_start, p_start + s_end, lang))

    chunks: list[Chunk] = []
    group: list[_Piece] = []

    def flush() -> None:
        if not group:
            return
        c_start, c_end = group[0].start, group[-1].end
        cid = f"{doc.id}:c{len(chunks)}"
        lang = group[0].lang
        sentences = [
            Sentence(
                id=f"{cid}:s{k}",
                doc_id=doc.id,
                chunk_id=cid,
                index=k,
                start=pc.start - c_start,
                end=pc.end - c_start,
                text=text[pc.start : pc.end],
                lang=lang,
            )
            for k, pc in enumerate(group)
        ]
        chunks.append(
            Chunk(
                id=cid,
                doc_id=doc.id,
                index=len(chunks),
                start=c_start,
                end=c_end,
                text=text[c_start:c_end],
                lang=lang,
                sentences=sentences,
            )
        )
        group.clear()

    for piece in pieces:
        if group:
            size = piece.end - group[0].start
            if piece.lang != group[0].lang or size > target_for(group[0].lang):
                flush()
        group.append(piece)
    flush()
    return chunks
