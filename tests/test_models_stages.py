"""NER, GLiNER and embedding stages, tested with small fakes (no model downloads)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from leankg.config import Config
from leankg.models import Document
from leankg.pipeline import Pipeline
from leankg.stages.entities.gliner_stage import GlinerStage
from leankg.stages.linking import LinkingStage
from leankg.stages.linking.chunk_embed import ChunkEmbedStage

from .conftest import requires_en_model
from .helpers import make_ctx

BASE = ("ingest", "preprocess", "dictionary", "regex")


def _run(
    text: str, stages: tuple[str, ...], domain: str = "health_stress", ctx: Any = None
) -> Document:
    ctx = ctx or make_ctx(domain)
    return Pipeline(ctx=ctx, stage_names=list(stages)).run([Document(id="t", text=text)])[0]


@requires_en_model
def test_ner_maps_model_labels_to_ontology_types() -> None:
    ctx = make_ctx("manufacturing")
    doc = _run("The Boeing 747 had a hydraulic leak.", (*BASE, "ner"), ctx=ctx)
    # PRODUCT -> Machine per models.yaml (if en_core_web_sm tags it)
    for m in doc.mentions:
        if m.method == "ner":
            assert m.type == "Machine"
            assert m.pattern_id == "ner:PRODUCT"


def test_ner_reports_missing_extra_models() -> None:
    from .conftest import has_module

    ctx = make_ctx("health_stress")
    _run("Stress causes insomnia.", (*BASE, "ner"), ctx=ctx)
    warned = any("en_ner_bc5cdr_md" in w for w in ctx.report.warnings)
    assert warned != has_module("en_ner_bc5cdr_md")


class FakeGliner:
    def predict_entities(
        self, text: str, labels: list[str], threshold: float
    ) -> list[dict[str, Any]]:
        out = []
        i = text.find("burnout syndrome")
        if i >= 0 and "disease or disorder" in labels:
            out.append({"start": i, "end": i + 16, "text": "burnout syndrome",
                        "label": "disease or disorder", "score": 0.91})  # fmt: skip
        j = text.find("nightmares")
        if j >= 0:
            out.append({"start": j, "end": j + 10, "text": "nightmares", "label": "symptom",
                        "score": 0.8})  # fmt: skip
        return out


def test_gliner_stage_with_fake_model(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_ctx("health_stress")
    monkeypatch.setitem(GlinerStage._models, "urchade/gliner_multi-v2.1", FakeGliner())
    doc = _run("He reported nightmares.", (*BASE, "gliner"), ctx=ctx)
    m = next(m for m in doc.mentions if m.method == "gliner")
    assert (m.text, m.type, m.confidence) == ("nightmares", "Symptom", 0.8)


def test_gliner_only_runs_on_sparse_sentences(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = make_ctx("health_stress")
    monkeypatch.setitem(GlinerStage._models, "urchade/gliner_multi-v2.1", FakeGliner())
    doc = _run("Stress and insomnia caused nightmares.", (*BASE, "gliner"), ctx=ctx)
    assert not [m for m in doc.mentions if m.method == "gliner"]  # already 2 entities


def test_gliner_missing_extra_is_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> Any:
        if name == "gliner":
            raise ImportError("no gliner")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(GlinerStage, "_models", {})
    ctx = make_ctx("health_stress")
    doc = _run("Nothing here.", (*BASE, "gliner"), ctx=ctx)
    assert doc.mentions == []
    assert any("gliner" in w for w in ctx.report.warnings)


class FakeEncoder:
    model_name = "fake"
    dimension = 3

    def encode(self, texts: list[str], kind: str = "query", batch_size: int = 32) -> Any:
        vecs = []
        for t in texts:
            low = t.lower()
            v = np.array([1.0 if "sleep" in low or "不眠" in t else 0.0,
                          1.0 if "worry" in low or "心配" in t else 0.0, 0.1])  # fmt: skip
            vecs.append(v / np.linalg.norm(v))
        return np.vstack(vecs)


def test_chunk_embeddings_with_fake_encoder() -> None:
    ctx = make_ctx("health_stress")
    stage = ChunkEmbedStage(ctx)
    stage._encoder = FakeEncoder()
    ctx.graph.metadata["embedding_model"] = "fake"
    doc = _run("Sleep matters.", ("ingest",), ctx=ctx)
    stage.process(doc)
    assert doc.chunks[0].embedding is not None
    assert len(doc.chunks[0].embedding) == 3


def test_embedding_linker_used_after_fuzzy_misses(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    from leankg.stages.linking import embed as embed_mod

    ctx = make_ctx("health_stress", Config())
    pack = ctx.require_pack()
    monkeypatch.setattr(embed_mod, "Encoder", lambda name: FakeEncoder())
    linker = embed_mod.EmbeddingLinker(pack, "fake", cache_dir=tmp_path)
    stage = LinkingStage(ctx)
    stage._embedder = linker
    from leankg.models import Mention

    m = Mention(id="m", doc_id="t", chunk_id="c", sent_id="s", start=0, end=14,
                text="trouble asleep", type="Condition", method="gliner", lang="en",
                confidence=0.8)  # fmt: skip
    cands = linker.candidates(m, threshold=0.5)
    assert cands
    assert pack.concepts[cands[0].ontology_id].type == "Condition"
    stage.link(m)
    assert m.link_method in ("embed", "fuzzy")
    assert m.entity_id == m.ontology_id
