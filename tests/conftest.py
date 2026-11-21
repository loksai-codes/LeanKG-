from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOMAINS = ROOT / "domains"


def has_module(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError):
        return False


requires_en_model = pytest.mark.skipif(
    not has_module("en_core_web_sm"), reason="en_core_web_sm not installed"
)
requires_ginza = pytest.mark.skipif(
    not (has_module("ginza") and has_module("ja_ginza")), reason="[ja] extra not installed"
)


@pytest.fixture(autouse=True)
def no_heavy_models(monkeypatch: pytest.MonkeyPatch) -> None:
    """Unit tests never download or load GLiNER / sentence-transformers models.

    Tests may still inject fakes (``GlinerStage._models[...]``, ``stage._encoder``,
    ``stage._embedder``); only the real loading paths are disabled.
    """
    from leankg.stages.entities.gliner_stage import GlinerStage
    from leankg.stages.linking import LinkingStage
    from leankg.stages.linking.chunk_embed import ChunkEmbedStage

    def gliner_model(self: GlinerStage) -> object:
        name = self.ctx.require_pack().models.gliner.model
        return GlinerStage._models.get(name)

    monkeypatch.setattr(GlinerStage, "real_model", GlinerStage.model, raising=False)
    monkeypatch.setattr(GlinerStage, "model", gliner_model)
    monkeypatch.setattr(ChunkEmbedStage, "encoder", lambda self: self._encoder)
    monkeypatch.setattr(LinkingStage, "embedder", lambda self: self._embedder)


@pytest.fixture
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run in an empty folder with no LEANKG_*/GROQ/NEO4J env vars."""
    for key in list(os.environ):
        if key.startswith(("LEANKG_", "GROQ_", "NEO4J_")):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    return tmp_path
