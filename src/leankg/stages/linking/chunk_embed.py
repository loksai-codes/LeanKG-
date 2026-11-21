"""Chunk embedding stage (``[embed]`` extra).

Embeds every chunk with the pack's multilingual sentence-transformers model, so the Neo4j
vector index works across languages. The model name and dimension are recorded in the
graph metadata. A no-op (with a RunReport warning) when the extra isn't installed.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from typing import Any, ClassVar

from leankg.models import Document
from leankg.stages.base import BaseStage, StageContext

log = logging.getLogger(__name__)


class ChunkEmbedStage(BaseStage):
    name: ClassVar[str] = "embed"

    def __init__(self, ctx: StageContext) -> None:
        super().__init__(ctx)
        self._encoder: Any = None
        self._failed = False

    def encoder(self) -> Any:
        if self._encoder is None and not self._failed:
            model = self.ctx.require_pack().models.embeddings.get("model", "")
            if not model:
                self._failed = True
                return None
            try:
                from leankg.stages.linking.embed import Encoder

                self._encoder = Encoder(model)
            except ImportError:
                self._failed = True
                msg = "embed: [embed] extra not installed; chunk embeddings skipped"
                log.warning(msg)
                self.ctx.report.warnings.append(msg)
                return None
            self.ctx.graph.metadata["embedding_model"] = model
            self.ctx.graph.metadata["embedding_dim"] = str(self._encoder.dimension)
        return self._encoder

    def process_many(self, docs_in: Iterable[Document]) -> list[Document]:
        docs = list(docs_in)
        chunks = [c for d in docs for c in d.chunks if c.embedding is None]
        if not chunks:
            return docs
        enc = self.encoder()
        if enc is None:
            return docs
        vectors = enc.encode([c.text for c in chunks], kind="passage")
        for chunk, vec in zip(chunks, vectors, strict=True):
            chunk.embedding = [round(float(x), 6) for x in vec]
        return docs

    def process(self, doc: Document) -> Document:
        return self.process_many([doc])[0]
