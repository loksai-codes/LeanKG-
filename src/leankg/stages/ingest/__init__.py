"""Ingest stage: clean text, detect language, chunk into sentences."""

from __future__ import annotations

from typing import ClassVar

from leankg.lang.detect import detect_language
from leankg.models import Document
from leankg.stages.base import BaseStage
from leankg.stages.ingest.chunker import chunk_document, clean_text
from leankg.stages.ingest.loaders import LoaderOptions, load_documents, load_file


class IngestStage(BaseStage):
    """Cleans text, sets ``doc.lang`` and builds chunks + sentences (if not done yet)."""

    name: ClassVar[str] = "ingest"

    def _split(self, text: str, lang: str) -> list[tuple[int, int]]:
        profile = self.ctx.get_profiles().get(lang)
        spans: list[tuple[int, int]] = profile.split_sentences(text)
        return spans

    def process(self, doc: Document) -> Document:
        if doc.chunks:
            return doc
        threshold = self.config.detect.cjk_threshold
        doc.text = clean_text(doc.text)
        doc.lang = detect_language(doc.text, threshold, default=doc.lang or "en")
        doc.chunks = chunk_document(
            doc, self._split, self.config.chunking.target_for, threshold=threshold
        )
        return doc


__all__ = ["IngestStage", "LoaderOptions", "load_documents", "load_file"]
