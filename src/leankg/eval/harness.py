"""Evaluation harness: run a setup over gold data and report metrics per language."""

from __future__ import annotations

import datetime as dt
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from leankg.domain.loader import resolve_pack_path
from leankg.eval.gold import GoldExample, load_gold
from leankg.eval.metrics import (
    PRF,
    entity_scores,
    linking_counts,
    prediction_from_doc,
    relation_scores,
)
from leankg.models import Document

log = logging.getLogger(__name__)


class LangEval(BaseModel):
    domain: str
    lang: str
    setup: str
    gold_file: str
    n_examples: int
    entity_exact: dict[str, float | int]
    entity_partial: dict[str, float | int]
    linking_accuracy: float | None
    linking_n: int
    relation: dict[str, float | int]
    llm_call_rate: float
    hard_case_rate: float
    cache_hit_rate: float
    llm_requests: int
    tokens_in: int
    tokens_out: int
    est_cost_usd: float
    cost_per_1k_docs_usd: float
    docs_per_min: float
    sentences_per_sec: float
    duration_s: float
    stages: list[str]
    skipped_stages: list[str]
    provider: str
    model: str
    budget_exhausted: bool = False
    warnings: list[str] = Field(default_factory=list)


class EvalReport(BaseModel):
    date: str
    domain: str
    setup: str
    results: list[LangEval]

    def to_markdown(self) -> str:
        head = (
            "| Domain | Lang | Setup | n | Ent P | Ent R | Ent F1 | Ent F1 (partial) | Link acc | "
            "Rel P | Rel R | Rel F1 | LLM call rate | Cost / 1k docs | docs/min |\n"
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"
        )
        rows = []
        for r in self.results:
            link = f"{r.linking_accuracy:.2f}" if r.linking_accuracy is not None else "–"
            rp, rr, rf = (
                (f"{r.relation['precision']:.2f}", f"{r.relation['recall']:.2f}",
                 f"{r.relation['f1']:.2f}")
                if r.relation
                else ("–", "–", "–")
            )  # fmt: skip
            rows.append(
                f"| {r.domain} | {r.lang} | {r.setup} | {r.n_examples} | "
                f"{r.entity_exact['precision']:.2f} | {r.entity_exact['recall']:.2f} | "
                f"{r.entity_exact['f1']:.2f} | {r.entity_partial['f1']:.2f} | {link} | "
                f"{rp} | {rr} | {rf} | {r.llm_call_rate * 100:.1f}% | "
                f"${r.cost_per_1k_docs_usd:.3f} | {r.docs_per_min:.0f} |"
            )
        return "\n".join([head, *rows])


def _align_to_clean(ex: GoldExample) -> GoldExample:
    """Re-map gold offsets onto the text as the ingest stage cleans it (spaces collapsed)."""
    from leankg.stages.ingest.chunker import clean_text

    cleaned = clean_text(ex.text)
    if cleaned == ex.text:
        return ex
    mapping: list[int] = []  # original index -> cleaned index
    j = 0
    for ch in ex.text:
        if j < len(cleaned) and (cleaned[j] == ch or (ch.isspace() and cleaned[j] == " ")):
            mapping.append(j)
            j += 1
        else:
            mapping.append(j)  # dropped char maps to the next kept position
    mapping.append(len(cleaned))
    data = ex.model_dump()
    data["text"] = cleaned
    for ent in data["entities"]:
        ent["start"], ent["end"] = mapping[ent["start"]], mapping[ent["end"]]
        ent["text"] = cleaned[ent["start"] : ent["end"]]
        ent.pop("occurrence", None)
    return GoldExample.model_validate(data)


def _filter_types(ex: GoldExample, keep: set[str]) -> GoldExample:
    """Keep only entities of the given types (relations between kept entities survive)."""
    index = {i: k for k, i in enumerate(i for i, e in enumerate(ex.entities) if e.type in keep)}
    data = ex.model_dump()
    data["entities"] = [e for i, e in enumerate(data["entities"]) if i in index]
    data["relations"] = [
        {**r, "head": index[r["head"]], "tail": index[r["tail"]]}
        for r in data["relations"]
        if r["head"] in index and r["tail"] in index
    ]
    return GoldExample.model_validate(data)


def gold_path(domain: str, lang: str, fixtures: bool = False) -> Path | None:
    """``eval/gold.<lang>.jsonl`` if present (or ``fixtures/gold.<lang>.jsonl``)."""
    root = resolve_pack_path(domain) / "eval"
    main = root / f"gold.{lang}.jsonl"
    fixture = root / "fixtures" / f"gold.{lang}.jsonl"
    if not fixtures and main.is_file():
        return main
    return fixture if fixture.is_file() else None


def evaluate_examples(
    examples: list[GoldExample],
    domain: str,
    setup: str,
    *,
    llm: str | None = None,
    skip: Iterable[str] = (),
    overrides: dict[str, Any] | None = None,
    gold_file: str = "",
    lang: str = "",
    types: Iterable[str] | None = None,
) -> LangEval:
    from leankg.pipeline import Pipeline

    pipe = Pipeline.from_domain(domain, setup=setup, llm=llm, skip=skip, overrides=overrides)
    examples = [_align_to_clean(ex) for ex in examples]
    keep = set(types) if types else None
    if keep is not None:
        examples = [_filter_types(ex, keep) for ex in examples]
    has_relations = any(ex.relations for ex in examples)
    docs = [Document(id=ex.id, text=ex.text, lang=ex.lang) for ex in examples]
    processed = pipe.run(docs)
    warnings: list[str] = []
    ent_exact, ent_partial, rel = PRF(), PRF(), PRF()
    link_ok = link_n = 0
    for ex, doc in zip(examples, processed, strict=True):
        if doc.text != ex.text:
            warnings.append(f"{ex.id}: text changed by cleaning; offsets may be off")
        pred = prediction_from_doc(doc)
        if keep is not None:
            pred.mentions = [m for m in pred.mentions if m.type in keep]
        e, p = entity_scores(ex, pred)
        ent_exact.add(e)
        ent_partial.add(p)
        ok, n = linking_counts(ex, pred)
        link_ok += ok
        link_n += n
        rel.add(relation_scores(ex, pred))
    report = pipe.report
    sents = max(report.sentences, 1)
    return LangEval(
        domain=domain,
        lang=lang or (examples[0].lang if examples else ""),
        setup=setup,
        gold_file=gold_file,
        n_examples=len(examples),
        entity_exact=ent_exact.summary(),
        entity_partial=ent_partial.summary(),
        linking_accuracy=round(link_ok / link_n, 4) if link_n else None,
        linking_n=link_n,
        relation=rel.summary() if has_relations else {},
        llm_call_rate=round(report.llm_call_rate, 4),
        hard_case_rate=round(report.hard_case_rate, 4),
        cache_hit_rate=round(report.cache_hit_rate, 4),
        llm_requests=report.llm_requests,
        tokens_in=report.tokens_in,
        tokens_out=report.tokens_out,
        est_cost_usd=round(report.est_cost_usd, 6),
        cost_per_1k_docs_usd=round(report.cost_per_1k_docs_usd, 4),
        docs_per_min=round(report.docs_per_min, 1),
        sentences_per_sec=round(sents / report.duration_s, 1) if report.duration_s else 0.0,
        duration_s=round(report.duration_s, 3),
        stages=report.stages,
        skipped_stages=report.skipped_stages,
        provider=report.provider,
        model=report.model,
        budget_exhausted=report.budget_exhausted,
        warnings=[*warnings, *report.warnings],
    )


def run_eval(
    domain: str,
    setup: str,
    langs: Iterable[str] = ("en", "ja"),
    *,
    gold: str | Path | None = None,
    fixtures: bool = False,
    llm: str | None = None,
    skip: Iterable[str] = (),
    overrides: dict[str, Any] | None = None,
    types: Iterable[str] | None = None,
) -> EvalReport:
    results = []
    skip = list(skip)
    for lang in langs:
        path = Path(gold) if gold else gold_path(domain, lang, fixtures)
        if path is None or not path.is_file():
            log.warning("no gold data for %s/%s", domain, lang)
            continue
        examples = [ex for ex in load_gold(path) if ex.lang == lang]
        if not examples:
            continue
        results.append(
            evaluate_examples(
                examples,
                domain,
                setup.upper(),
                llm=llm,
                skip=skip,
                overrides=overrides,
                gold_file=str(path),
                lang=lang,
                types=types,
            )
        )
    return EvalReport(
        date=dt.date.today().isoformat(), domain=domain, setup=setup.upper(), results=results
    )


def save_report(report: EvalReport, folder: str | Path = "reports") -> Path:
    out = Path(folder)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{report.date}_{report.domain}_{report.setup}.json"
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


# ------------------------------------------------------------------ baseline
def baseline_key(r: LangEval) -> str:
    return f"{r.domain}/{r.lang}/{r.setup}"


def update_baseline(report: EvalReport, path: str | Path) -> Path:
    p = Path(path)
    data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}
    for r in report.results:
        data[baseline_key(r)] = {
            "entity_f1": r.entity_exact["f1"],
            "relation_f1": r.relation.get("f1"),
            "n_examples": r.n_examples,
            "stages": r.stages,
        }
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def check_baseline(report: EvalReport, path: str | Path, tolerance: float = 0.02) -> list[str]:
    """Problems where F1 dropped more than ``tolerance`` (0.02 = 2 points) vs the baseline."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    problems = []
    for r in report.results:
        base = data.get(baseline_key(r))
        if base is None:
            problems.append(f"{baseline_key(r)}: no baseline entry (run with --update-baseline)")
            continue
        for metric, current in (
            ("entity_f1", r.entity_exact.get("f1")),
            ("relation_f1", r.relation.get("f1")),
        ):
            if current is None or base.get(metric) is None:
                continue
            if float(current) < float(base[metric]) - tolerance:
                problems.append(
                    f"{baseline_key(r)}: {metric} {float(current):.4f} < baseline "
                    f"{float(base[metric]):.4f} "
                    f"- {tolerance:.2f}"
                )
    return problems
