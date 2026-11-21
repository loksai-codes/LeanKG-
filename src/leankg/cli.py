"""Command-line interface (Typer)."""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Annotated

import typer

from leankg import __version__

app = typer.Typer(
    name="leankg",
    help="Documents (EN + JA) to a knowledge graph: rules first, a little LLM.",
    no_args_is_help=True,
    add_completion=False,
)

DomainOpt = Annotated[str, typer.Option("--domain", "-d", help="Domain pack name or path.")]
ConfigOpt = Annotated[
    Path | None, typer.Option("--config", help="leankg.toml (default: search upwards).")
]


def _version(value: bool) -> None:
    if value:
        typer.echo(f"leankg {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Debug logging.")] = False,
) -> None:
    """leankg command line."""
    warnings.filterwarnings("ignore", message=".*SOCKS support.*")
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@app.command()
def build(
    path: Annotated[Path, typer.Argument(help="File or folder of documents.", exists=True)],
    domain: DomainOpt = "health_stress",
    llm: Annotated[
        str | None, typer.Option(help="none | groq | ollama | fake (default: config)")
    ] = None,
    out: Annotated[str, typer.Option(help="json | csv | graphml | neo4j | none")] = "json",
    out_path: Annotated[Path, typer.Option(help="Output file or folder.")] = Path("out"),
    setup: Annotated[str | None, typer.Option(help="Stage preset A | B | C | D.")] = None,
    llm_budget: Annotated[int | None, typer.Option(help="Max LLM requests this run.")] = None,
    skip: Annotated[list[str] | None, typer.Option(help="Stage to skip (repeatable).")] = None,
    csv_text_column: Annotated[str, typer.Option(help="CSV column holding text.")] = "text",
    csv_id_column: Annotated[str | None, typer.Option(help="CSV column holding ids.")] = None,
    config: ConfigOpt = None,
) -> None:
    """Build a knowledge graph from documents and print the RunReport."""
    from leankg.pipeline import Pipeline
    from leankg.report import render_report
    from leankg.stages.ingest import LoaderOptions

    pipe = Pipeline.from_domain(
        domain, llm=llm, llm_budget=llm_budget, setup=setup, config_path=config, skip=skip or ()
    )
    opts = LoaderOptions(csv_text_column=csv_text_column, csv_id_column=csv_id_column)
    report = pipe.build(path, out=None if out == "none" else out, out_path=out_path,
                        loader_options=opts)  # fmt: skip
    typer.echo(render_report(report))
    if out not in ("none", "neo4j"):
        typer.echo(f"wrote {out} to {out_path}")


@app.command("eval")
def eval_cmd(
    domain: DomainOpt = "health_stress",
    setup: Annotated[str, typer.Option(help="A | B | C | D")] = "A",
    lang: Annotated[str, typer.Option(help="en | ja | all")] = "all",
    gold: Annotated[
        Path | None, typer.Option(help="Gold JSONL (default: the pack's eval/gold.<lang>.jsonl)")
    ] = None,
    fixtures: Annotated[bool, typer.Option(help="Use the pack's small CI fixtures.")] = False,
    llm: Annotated[str | None, typer.Option(help="Override the LLM provider.")] = None,
    skip: Annotated[list[str] | None, typer.Option(help="Stage to skip (repeatable).")] = None,
    reports: Annotated[Path, typer.Option(help="Folder for the JSON report.")] = Path("reports"),
    baseline: Annotated[
        Path | None, typer.Option(help="Fail if F1 drops more than --tolerance below this.")
    ] = None,
    tolerance: Annotated[float, typer.Option(help="Allowed F1 drop (0.02 = 2 points).")] = 0.02,
    update_baseline: Annotated[bool, typer.Option(help="Write results into --baseline.")] = False,
    types: Annotated[
        list[str] | None, typer.Option(help="Only evaluate these entity types (repeatable).")
    ] = None,
) -> None:
    """Evaluate a setup against gold data; prints a markdown table and writes a JSON report."""
    from leankg.eval.harness import check_baseline, run_eval, save_report
    from leankg.eval.harness import update_baseline as write_baseline

    langs = ["en", "ja"] if lang == "all" else [lang]
    report = run_eval(
        domain, setup, langs, gold=gold, fixtures=fixtures, llm=llm, skip=skip or (), types=types
    )
    if not report.results:
        typer.echo("no gold data found", err=True)
        raise typer.Exit(2)
    typer.echo(report.to_markdown())
    for r in report.results:
        for w in sorted(set(r.warnings)):
            typer.echo(f"warning [{r.lang}]: {w}", err=True)
    typer.echo(f"report: {save_report(report, reports)}")
    if baseline is not None:
        if update_baseline:
            typer.echo(f"baseline updated: {write_baseline(report, baseline)}")
        else:
            problems = check_baseline(report, baseline, tolerance)
            for p in problems:
                typer.echo(f"REGRESSION: {p}", err=True)
            if problems:
                raise typer.Exit(1)
            typer.echo("baseline check passed")


labelstudio_app = typer.Typer(help="Label Studio config, task files and export conversion.")
app.add_typer(labelstudio_app, name="labelstudio")


@labelstudio_app.command("config")
def ls_config(
    domain: DomainOpt = "health_stress",
    lang: Annotated[str, typer.Option(help="Language for label hints.")] = "ja",
) -> None:
    """Print a Label Studio labeling config for the pack's ontology."""
    from leankg.domain.loader import load_pack
    from leankg.eval.label_studio import labeling_config

    typer.echo(labeling_config(load_pack(domain), lang))


@labelstudio_app.command("tasks")
def ls_tasks(
    sentences: Annotated[Path, typer.Argument(help="Text file, one sentence per line.")],
    domain: DomainOpt = "health_stress",
    lang: Annotated[str, typer.Option(help="en | ja")] = "ja",
    out: Annotated[Path, typer.Option(help="Output tasks JSON.")] = Path("tasks.json"),
    preannotate: Annotated[
        bool, typer.Option(help="Add leankg setup-B output as predictions.")
    ] = False,
) -> None:
    """Create a Label Studio import file (optionally pre-annotated by leankg)."""
    import json

    from leankg.eval.label_studio import make_tasks
    from leankg.eval.preannotate import preannotate as run_pre

    texts = [ln.strip() for ln in sentences.read_text(encoding="utf-8").splitlines() if ln.strip()]
    preds = run_pre(texts, domain, lang) if preannotate else None
    tasks = make_tasks(texts, lang, domain[:2], preds)
    out.write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    typer.echo(f"wrote {len(tasks)} tasks to {out}")


@labelstudio_app.command("convert")
def ls_convert(
    export: Annotated[Path, typer.Argument(help="Label Studio JSON export.")],
    out: Annotated[Path, typer.Option(help="Gold JSONL to write.")] = Path("gold.jsonl"),
    lang: Annotated[str | None, typer.Option(help="Force language (default: task data).")] = None,
    domain: Annotated[
        str | None, typer.Option(help="Validate labels against this pack's ontology.")
    ] = None,
) -> None:
    """Convert a Label Studio export to the leankg gold format."""
    from leankg.eval.gold import dump_gold
    from leankg.eval.label_studio import convert_export, load_export

    examples, warnings = convert_export(load_export(export), lang)
    if domain:
        from leankg.domain.loader import load_pack

        pack = load_pack(domain)
        for ex in examples:
            for e in ex.entities:
                if e.type not in pack.ontology.entities:
                    warnings.append(f"{ex.id}: unknown entity type {e.type!r}")
            for r in ex.relations:
                if r.type not in pack.ontology.relations:
                    warnings.append(f"{ex.id}: unknown relation {r.type!r}")
    for w in warnings:
        typer.echo(f"warning: {w}", err=True)
    dump_gold(examples, out)
    typer.echo(f"wrote {len(examples)} examples to {out}")


@app.command("review-llm")
def review_llm(domain: DomainOpt = "health_stress") -> None:
    """Suggest dictionary/trigger entries from logged LLM answers. TODO: M4."""
    typer.echo("review-llm: not implemented yet (M4)")
    raise typer.Exit(1)


@app.command("llm-models")
def llm_models() -> None:
    """List models served by the configured LLM provider. TODO: M4."""
    typer.echo("llm-models: not implemented yet (M4)")
    raise typer.Exit(1)


@app.command("import-owl")
def import_owl(
    source: Annotated[Path, typer.Argument(help="OWL/RDF/TTL file.")],
    out: Annotated[Path, typer.Option(help="Output ontology.yaml")] = Path("ontology.yaml"),
) -> None:
    """Convert an OWL/RDF ontology into a pack ontology.yaml. TODO: M5."""
    typer.echo("import-owl: not implemented yet (M5)")
    raise typer.Exit(1)
