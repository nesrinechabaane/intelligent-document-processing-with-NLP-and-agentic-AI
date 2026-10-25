"""Command line interface: ``idp process | evaluate | generate-samples | serve``."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

import click

from . import __version__
from .config import ConfigError, Settings
from .evaluation import evaluate_directory
from .ingestion import SUPPORTED_SUFFIXES
from .models import Severity
from .pipeline import process_many, write_outputs
from .reporting import overall_severity
from .samples import generate_samples

_ICON = {Severity.CRITICAL: "🔴", Severity.WARNING: "🟠", Severity.INFO: "🟢"}


def _settings(**overrides: Any) -> Settings:
    try:
        return Settings.from_env(**overrides)
    except ConfigError as exc:
        raise click.ClickException(str(exc)) from exc


def _expand(paths: tuple[Path, ...]) -> list[Path]:
    """Expand directories into the supported files they contain."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files += sorted(p for p in path.iterdir() if p.suffix.lower() in SUPPORTED_SUFFIXES)
        else:
            files.append(path)
    return files


@click.group()
@click.version_option(__version__, prog_name="idp")
@click.option("-v", "--verbose", is_flag=True, help="Enable debug logging.")
def main(verbose: bool) -> None:
    """Intelligent Document Processing with NLP and an agentic decision loop."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )


@main.command()
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True, path_type=Path))
@click.option("-o", "--output-dir", type=click.Path(path_type=Path), help="Where to write results.")
@click.option(
    "--llm",
    "llm_provider",
    type=click.Choice(["none", "anthropic"]),
    help="Let an LLM choose the actions (default: deterministic rules).",
)
def process(paths: tuple[Path, ...], output_dir: Path | None, llm_provider: str | None) -> None:
    """Process documents (files or folders): extract, verify, act, report."""
    settings = _settings(output_dir=output_dir, llm_provider=llm_provider)
    files = _expand(paths)
    if not files:
        raise click.ClickException("No supported document found.")
    batch = process_many(files, settings)

    for name, result in batch.results.items():
        json_path, md_path = write_outputs(result, settings.output_dir)
        icon = _ICON[overall_severity(result.findings)]
        tools = ", ".join(a.tool for a in result.actions if a.ok) or "none"
        click.echo(f"{icon} {Path(name).name}: {len(result.findings)} finding(s); actions: {tools}")
        click.echo(f"    report: {md_path}")
    for name, error in batch.errors.items():
        click.echo(f"❌ {Path(name).name}: {error}", err=True)
    click.echo(
        f"\n{len(batch.results)} processed, {len(batch.errors)} failed → {settings.output_dir}"
    )
    if batch.errors:
        sys.exit(1)


@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--min-f1", type=float, default=None, help="Exit with code 1 if measurement F1 is lower."
)
def evaluate(directory: Path, min_f1: float | None) -> None:
    """Score the pipeline against '<name>.expected.json' ground-truth files."""
    report = evaluate_directory(directory, _settings())
    if not report.scores:
        raise click.ClickException(f"No documents with ground truth found in {directory}")
    click.echo(report.format())
    if min_f1 is not None and report.measurement_prf[2] < min_f1:
        click.echo(f"\nFAILED: measurement F1 below {min_f1:.2f}", err=True)
        sys.exit(1)


@main.command("generate-samples")
@click.option(
    "-d",
    "--directory",
    type=click.Path(path_type=Path),
    default=Path("data"),
    show_default=True,
    help="Root folder: creates <dir>/samples and <dir>/samples_hard.",
)
def generate_samples_cmd(directory: Path) -> None:
    """Write synthetic documents (txt, pdf, png) and their ground truth."""
    files = generate_samples(directory)
    click.echo(f"Wrote {len(files)} documents under {directory}/ (samples, samples_hard)")


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True)
@click.option("--port", default=8000, show_default=True, type=int)
def serve(host: str, port: int) -> None:
    """Start the FastAPI server (requires the 'api' extra)."""
    try:
        import uvicorn

        from .api import create_app
    except ImportError as exc:
        raise click.ClickException("Install the API extra: pip install 'idp-agent[api]'") from exc
    uvicorn.run(create_app(_settings()), host=host, port=port)


if __name__ == "__main__":  # pragma: no cover
    main()
