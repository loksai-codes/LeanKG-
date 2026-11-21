from typing import ClassVar

import pytest

from leankg.config import Config
from leankg.models import Document
from leankg.pipeline import DEFAULT_STAGES, Pipeline, resolve_stage_class
from leankg.stages.base import BaseStage, Stage, StageContext


class Upper(BaseStage):
    name: ClassVar[str] = "upper"

    def process(self, doc: Document) -> Document:
        doc.text = doc.text.upper()
        return doc


def test_custom_stages_run_in_order_and_can_be_skipped() -> None:
    ctx = StageContext(config=Config())
    pipe = Pipeline([Upper(ctx)], ctx=ctx)
    assert pipe.process(Document(id="d", text="abc")).text == "ABC"
    pipe = Pipeline([Upper(ctx)], ctx=ctx, skip=["upper"])
    assert pipe.process(Document(id="d", text="abc")).text == "abc"


def test_every_registered_stage_resolves_and_satisfies_protocol() -> None:
    ctx = StageContext(config=Config())
    for name in DEFAULT_STAGES:
        stage = resolve_stage_class(name)(ctx)
        assert isinstance(stage, Stage)
        assert stage.name == name


def test_unknown_stage_name() -> None:
    with pytest.raises(KeyError):
        resolve_stage_class("nope")


def test_report_records_stages() -> None:
    pipe = Pipeline(config=Config(), stage_names=["ingest", "write"], skip=["write"])
    pipe.run([Document(id="d", text="x")])
    assert pipe.report.stages == ["ingest"]
    assert pipe.report.skipped_stages == ["write"]
