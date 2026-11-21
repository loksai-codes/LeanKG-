"""Command-line interface (Typer)."""

from __future__ import annotations

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


def _version(value: bool) -> None:
    if value:
        typer.echo(f"leankg {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_version, is_eager=True, help="Show version.")
    ] = False,
) -> None:
    """leankg command line."""


@app.command()
def build(
    path: Annotated[Path, typer.Argument(help="File or folder of documents.")],
    domain: Annotated[str, typer.Option(help="Domain pack name or path.")] = "health_stress",
    llm: Annotated[str, typer.Option(help="none | groq | ollama | fake")] = "none",
) -> None:
    """Build a knowledge graph from documents. TODO: M1."""
    typer.echo("build: not implemented yet (M1)")
    raise typer.Exit(1)


@app.command("eval")
def eval_cmd(
    domain: Annotated[str, typer.Option(help="Domain pack name or path.")] = "health_stress",
    setup: Annotated[str, typer.Option(help="A | B | C | D")] = "A",
    lang: Annotated[str, typer.Option(help="en | ja | all")] = "all",
) -> None:
    """Evaluate against gold data. TODO: M3."""
    typer.echo("eval: not implemented yet (M3)")
    raise typer.Exit(1)


@app.command("review-llm")
def review_llm(
    domain: Annotated[str, typer.Option(help="Domain pack name or path.")] = "health_stress",
) -> None:
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
