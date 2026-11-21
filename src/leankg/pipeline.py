"""Pipeline: runs a configured list of stages over documents."""

from __future__ import annotations

import importlib
import time
from collections.abc import Iterable, Sequence
from typing import Any

from leankg.config import Config, load_config
from leankg.models import Document, RunReport
from leankg.stages.base import BaseStage, NoOpStage, Stage, StageContext

# name -> "module:Class". Order here is the default execution order.
STAGE_REGISTRY: dict[str, str] = {
    "ingest": "leankg.stages.ingest:IngestStage",
    "preprocess": "leankg.stages.preprocess:PreprocessStage",
    "dictionary": "leankg.stages.entities:DictionaryStage",
    "regex": "leankg.stages.entities:RegexStage",
    "ner": "leankg.stages.entities:NerStage",
    "gliner": "leankg.stages.entities:GlinerStage",
    "linking": "leankg.stages.linking:LinkingStage",
    "dependency": "leankg.stages.relations:DependencyStage",
    "trigger": "leankg.stages.relations:TriggerStage",
    "cooc": "leankg.stages.relations:CoocStage",
    "negation": "leankg.stages.relations:NegationStage",
    "validate": "leankg.stages.validate:ValidateStage",
    "route": "leankg.stages.route:RouteStage",
    "llm": "leankg.stages.route:LLMStage",
    "write": "leankg.stages.write:WriteStage",
}
DEFAULT_STAGES: tuple[str, ...] = tuple(STAGE_REGISTRY)


def resolve_stage_class(name: str) -> type[BaseStage]:
    """Import a stage class by registry name; unknown-but-registered → no-op placeholder."""
    if name not in STAGE_REGISTRY:
        raise KeyError(f"unknown stage {name!r}; known: {', '.join(STAGE_REGISTRY)}")
    module_name, _, cls_name = STAGE_REGISTRY[name].partition(":")
    module = importlib.import_module(module_name)
    cls = getattr(module, cls_name, None)
    if cls is None:
        # TODO: stage not built yet -> placeholder that passes documents through.
        return type(cls_name, (NoOpStage,), {"name": name})
    if not isinstance(cls, type) or not issubclass(cls, BaseStage):
        raise TypeError(f"{STAGE_REGISTRY[name]} is not a BaseStage subclass")
    return cls


class Pipeline:
    """An ordered list of stages plus the shared :class:`StageContext`."""

    def __init__(
        self,
        stages: Sequence[Stage] | None = None,
        *,
        ctx: StageContext | None = None,
        config: Config | None = None,
        stage_names: Sequence[str] | None = None,
        skip: Iterable[str] = (),
    ) -> None:
        self.ctx = ctx or StageContext(config=config or load_config())
        skipped = set(skip)
        if stages is not None:
            self.stages: list[Stage] = [s for s in stages if s.name not in skipped]
        else:
            names = [n for n in (stage_names or DEFAULT_STAGES) if n not in skipped]
            self.stages = [resolve_stage_class(n)(self.ctx) for n in names]
        self.skipped = sorted(skipped)

    @property
    def stage_names(self) -> list[str]:
        return [s.name for s in self.stages]

    def run(self, docs: Iterable[Document]) -> list[Document]:
        """Run every stage over every document. Returns the processed documents."""
        started = time.perf_counter()
        current = list(docs)
        for stage in self.stages:
            many: Any = getattr(stage, "process_many", None)
            current = list(many(current)) if callable(many) else [stage.process(d) for d in current]
        report = self.ctx.report
        report.duration_s += time.perf_counter() - started
        report.stages = self.stage_names
        report.skipped_stages = self.skipped
        return current

    def process(self, doc: Document) -> Document:
        return self.run([doc])[0]

    @property
    def report(self) -> RunReport:
        return self.ctx.report
