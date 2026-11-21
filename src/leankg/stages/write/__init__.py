"""Write stage: merge each processed document into the corpus graph.

Exporters (JSON/CSV/GraphML/Neo4j) run once at the end on the merged graph.
"""

from __future__ import annotations

from typing import ClassVar

from leankg.models import Document
from leankg.stages.base import BaseStage


class WriteStage(BaseStage):
    name: ClassVar[str] = "write"

    def process(self, doc: Document) -> Document:
        if self.ctx.pack is not None and not self.ctx.graph.domain:
            self.ctx.graph.domain = self.ctx.pack.name
        self.ctx.graph.add_document(doc)
        return doc


__all__ = ["WriteStage"]
