"""Command-line interface (Typer)."""

from __future__ import annotations

import logging
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
) -> None:
    """Evaluate against gold data. TODO: M3."""
    typer.echo("eval: not implemented yet (M3)")
    raise typer.Exit(1)


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
