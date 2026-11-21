"""Multilingual embedding linker and chunk embedder (``[embed]`` extra).

One sentence-transformers model (configured per pack in ``models.yaml``) embeds ontology
surfaces in every language, mentions and chunks, so a Japanese mention can link to an
English-labelled concept and Neo4j vector search works across languages. Concept surface
embeddings are cached on disk, keyed by model name + surfaces.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, ClassVar

from leankg.domain.pack import DomainPack
from leankg.models import LinkCandidate, Mention

log = logging.getLogger(__name__)


def _prefix(model_name: str, kind: str) -> str:
    """E5 models expect ``query:``/``passage:`` prefixes; others take raw text."""
    return f"{kind}: " if "e5" in model_name.lower() else ""


class Encoder:
    """Thin, cached wrapper around ``SentenceTransformer``."""

    _models: ClassVar[dict[str, Any]] = {}

    def __init__(self, model_name: str) -> None:
        from sentence_transformers import SentenceTransformer  # ImportError → extra missing

        if model_name not in self._models:
            self._models[model_name] = SentenceTransformer(model_name, device="cpu")
        self.model = self._models[model_name]
        self.model_name = model_name

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str], kind: str = "query", batch_size: int = 32) -> Any:
        prefix = _prefix(self.model_name, kind)
        return self.model.encode(
            [prefix + t for t in texts],
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )


class EmbeddingLinker:
    def __init__(self, pack: DomainPack, model_name: str, cache_dir: str | Path) -> None:
        self.encoder = Encoder(model_name)
        self.pack = pack
        self.surfaces: list[str] = []
        self.ids: list[str] = []
        for concept in pack.concepts.values():
            for _lang, surface in concept.all_surfaces():
                self.surfaces.append(surface)
                self.ids.append(concept.id)
        self.matrix = self._load_or_encode(Path(cache_dir))

    def _load_or_encode(self, cache_dir: Path) -> Any:
        import numpy as np

        key = hashlib.sha256(
            json.dumps([self.encoder.model_name, self.surfaces], ensure_ascii=False).encode()
        ).hexdigest()[:16]
        path = cache_dir / f"{self.pack.name}_{key}.npy"
        if path.is_file():
            return np.load(path)
        matrix = self.encoder.encode(self.surfaces, kind="query")
        try:
            cache_dir.mkdir(parents=True, exist_ok=True)
            np.save(path, matrix)
        except OSError as exc:  # pragma: no cover - read-only cache dir
            log.debug("could not cache embeddings: %s", exc)
        return matrix

    def candidates(self, mention: Mention, threshold: float) -> list[LinkCandidate]:
        vec = self.encoder.encode([mention.text], kind="query")[0]
        sims = self.matrix @ vec
        best: dict[str, float] = {}
        for i, score in enumerate(sims.tolist()):
            cid = self.ids[i]
            if self.pack.concepts[cid].type != mention.type or score < threshold:
                continue
            best[cid] = max(best.get(cid, 0.0), float(score))
        ranked = sorted(best.items(), key=lambda kv: (-kv[1], kv[0]))
        return [
            LinkCandidate(entity_id=cid, ontology_id=cid, score=s, method="embed")
            for cid, s in ranked
        ]
