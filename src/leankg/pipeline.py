"""Pipeline: runs a configured list of stages over documents."""

from __future__ import annotations

import importlib
import logging
import time
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from leankg.config import Config, load_config
from leankg.graph import KnowledgeGraph
from leankg.models import Document, RunReport
from leankg.stages.base import BaseStage, NoOpStage, Stage, StageContext

log = logging.getLogger(__name__)

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
    "embed": "leankg.stages.linking:ChunkEmbedStage",
    "write": "leankg.stages.write:WriteStage",
}
DEFAULT_STAGES: tuple[str, ...] = tuple(STAGE_REGISTRY)


@dataclass(frozen=True)
class Setup:
    """An evaluation setup = which stages run + a few options."""

    name: str
    description: str
    skip: tuple[str, ...] = ()
    overrides: dict[str, Any] = field(default_factory=dict)
    route_all: bool = False
    needs_llm: bool = False


SETUPS: dict[str, Setup] = {
    "A": Setup(
        "A",
        "rules only (dictionary, regex, fuzzy linking, patterns, triggers)",
        skip=("ner", "gliner", "llm", "embed"),
        overrides={"linking.use_embeddings": False},
    ),
    "B": Setup("B", "rules + statistical models (NER, GLiNER, embeddings)", skip=("llm",)),
    "C": Setup("C", "full leankg: rules + models + LLM fallback for hard cases", needs_llm=True),
    "D": Setup(
        "D",
        "LLM-only relations: same entities, every sentence with >= 2 entities goes to the LLM",
        skip=("dependency", "trigger", "cooc", "negation"),
        route_all=True,
        needs_llm=True,
    ),
}


def resolve_stage_class(name: str) -> type[BaseStage]:
    """Import a stage class by registry name; registered-but-unbuilt → no-op placeholder."""
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

    # ------------------------------------------------------------ factories
    @classmethod
    def from_domain(
        cls,
        domain: str | Path,
        *,
        llm: str | None = None,
        llm_budget: int | None = None,
        setup: str | None = None,
        config: Config | None = None,
        config_path: str | Path | None = None,
        skip: Iterable[str] = (),
        overrides: dict[str, Any] | None = None,
    ) -> Pipeline:
        """Build a pipeline for a domain pack.

        ``llm`` overrides ``[llm].provider``; ``setup`` is one of ``A``/``B``/``C``/``D``.
        """
        from leankg.domain.loader import load_pack
        from leankg.lang.base import ProfileRegistry
        from leankg.llm import make_client

        chosen = SETUPS[setup.upper()] if setup else None
        all_overrides: dict[str, Any] = dict(chosen.overrides if chosen else {})
        all_overrides.update(overrides or {})
        if llm is not None:
            all_overrides["llm.provider"] = llm
        if llm_budget is not None:
            all_overrides["llm.budget_calls"] = llm_budget
        if config is None:
            config = load_config(config_path, overrides=all_overrides)
        else:
            config = _apply_overrides(config, all_overrides)
        pack = load_pack(domain)
        ctx = StageContext(
            config=config,
            pack=pack,
            profiles=ProfileRegistry(),
            graph=KnowledgeGraph(domain=pack.name),
        )
        ctx.report.domain = pack.name
        ctx.report.provider = config.llm.provider
        ctx.report.model = config.llm.model if config.llm.provider != "none" else ""
        ctx.llm = make_client(config.llm)
        if chosen is not None:
            ctx.extras["route_all"] = chosen.route_all
            ctx.extras["setup"] = chosen.name
        skipped = [*(chosen.skip if chosen else ()), *skip]
        return cls(ctx=ctx, skip=skipped)

    # ------------------------------------------------------------------ run
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
        finalize_report(report, current, self.ctx.graph, self.ctx)
        return current

    def process(self, doc: Document) -> Document:
        return self.run([doc])[0]

    def build(
        self,
        source: str | Path | Iterable[Document],
        *,
        out: str | None = None,
        out_path: str | Path = "out",
        neo4j_uri: str | None = None,
        loader_options: Any = None,
    ) -> RunReport:
        """Load documents, run the pipeline, export the graph; returns the RunReport.

        ``out`` is ``json`` | ``csv`` | ``graphml`` | ``neo4j`` | ``None`` (no export).
        Passing ``neo4j_uri`` implies ``out="neo4j"``.
        """
        from leankg.stages.ingest import load_documents

        if isinstance(source, (str, Path)):
            docs = load_documents(source, loader_options)
        else:
            docs = list(source)
        self.run(docs)
        if neo4j_uri is not None:
            out = "neo4j"
            self.ctx.config.neo4j.uri = neo4j_uri
        if out:
            self.export(out, out_path)
        return self.report

    def export(self, out: str, out_path: str | Path = "out") -> Any:
        from leankg.export import export_csv, export_graphml, export_json

        g = self.ctx.graph
        unverified = self.ctx.config.write_unverified
        if out == "json":
            return export_json(g, out_path, unverified)
        if out == "csv":
            return export_csv(g, out_path, unverified)
        if out == "graphml":
            return export_graphml(g, out_path, unverified)
        if out == "neo4j":
            from leankg.export.neo4j_writer import Neo4jWriter

            cfg = self.ctx.config.neo4j
            if cfg.password is None:
                raise RuntimeError("set NEO4J_PASSWORD (env or .env) to write to Neo4j")
            with Neo4jWriter(
                cfg.uri, cfg.user, cfg.password.get_secret_value(), cfg.database, cfg.batch_size
            ) as writer:
                return writer.write_graph(g, unverified)
        raise ValueError(f"unknown output {out!r} (json | csv | graphml | neo4j)")

    @property
    def report(self) -> RunReport:
        return self.ctx.report

    @property
    def graph(self) -> KnowledgeGraph:
        return self.ctx.graph


def _apply_overrides(config: Config, overrides: dict[str, Any]) -> Config:
    if not overrides:
        return config
    data = config.model_dump()
    for dotted, value in overrides.items():
        target = data
        *parents, leaf = dotted.split(".")
        for part in parents:
            target = target.setdefault(part, {})
        target[leaf] = value
    new = Config.model_validate(data)
    new.llm.api_key = config.llm.api_key
    new.neo4j.password = config.neo4j.password
    return new


def finalize_report(
    report: RunReport, docs: list[Document], graph: KnowledgeGraph, ctx: StageContext
) -> None:
    """Fill document/sentence/mention/entity/triple counts, overall and per language."""
    for key in ("docs", "chunks", "sentences", "mentions", "entities", "triples",
                "triples_negative", "triples_unverified", "hard_case_sentences"):  # fmt: skip
        setattr(report, key, 0)
        for stats in report.by_lang.values():
            setattr(stats, key, 0)
    for doc in docs:
        report.docs += 1
        report.lang(doc.lang).docs += 1
        for chunk in doc.chunks:
            report.chunks += 1
            report.lang(chunk.lang).chunks += 1
            for _sent in chunk.sentences:
                report.sentences += 1
                report.lang(chunk.lang).sentences += 1
        for m in doc.mentions:
            report.mentions += 1
            report.lang(m.lang).mentions += 1
        hard_sents = {(hc.sent_id, hc.lang) for hc in doc.hard_cases}
        for _sid, lang in hard_sents:
            report.hard_case_sentences += 1
            report.lang(lang).hard_case_sentences += 1
    entities = graph.entities.values() if graph.entities else [e for d in docs for e in d.entities]
    for ent in entities:
        report.entities += 1
        for lang in ent.lang_seen:
            report.lang(lang).entities += 1
    triples = (
        list(graph.triples.values()) if graph.triples else [t for d in docs for t in d.triples]
    )
    for t in triples:
        langs = t.langs or sorted({p.lang for p in t.provenance})
        if t.status == "accepted":
            report.triples += 1
            for lang in langs:
                report.lang(lang).triples += 1
        elif t.status == "negative":
            report.triples_negative += 1
            for lang in langs:
                report.lang(lang).triples_negative += 1
        elif t.status in ("unverified", "candidate"):
            report.triples_unverified += 1
            for lang in langs:
                report.lang(lang).triples_unverified += 1
