"""End-to-end orchestration: ingest -> extract -> verify -> act -> report."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .agent import DocumentAgent
from .config import Settings
from .entities import enrich_with_spacy
from .extraction import extract_document
from .ingestion import IngestionError, load_document
from .llm import LLMError, build_llm
from .models import ProcessingResult
from .planner import LLMPlanner, Planner, RulePlanner
from .reporting import render_report
from .validation import validate

LOGGER = logging.getLogger(__name__)


def build_planner(settings: Settings) -> Planner:
    """Pick the planner from settings; degrade to rules if the LLM is unusable."""
    rules = RulePlanner(settings.min_confidence)
    try:
        llm = build_llm(settings)
    except LLMError as exc:
        LOGGER.warning("LLM disabled: %s", exc)
        return rules
    return LLMPlanner(llm, fallback=rules) if llm else rules


def build_agent(settings: Settings) -> DocumentAgent:
    return DocumentAgent(settings, planner=build_planner(settings))


def process_text(
    text: str,
    source: str = "<text>",
    settings: Settings | None = None,
    agent: DocumentAgent | None = None,
) -> ProcessingResult:
    """Run the whole pipeline on raw text."""
    settings = settings or Settings.from_env()
    agent = agent or build_agent(settings)

    document = enrich_with_spacy(extract_document(text, source=source), text)
    findings = validate(document)
    outcome = agent.run(document, findings)
    report = render_report(document, findings, outcome.actions, outcome.notes)
    return ProcessingResult(
        document=document,
        findings=findings,
        actions=outcome.actions,
        report_markdown=report,
        planner=outcome.planner,
        notes=outcome.notes,
    )


def process_file(
    path: str | Path,
    settings: Settings | None = None,
    agent: DocumentAgent | None = None,
    source: str | None = None,
) -> ProcessingResult:
    """Process one file; ``source`` overrides the name shown in reports."""
    settings = settings or Settings.from_env()
    text = load_document(path, ocr_lang=settings.ocr_lang)
    return process_text(text, source=source or Path(path).name, settings=settings, agent=agent)


@dataclass
class BatchResult:
    results: dict[str, ProcessingResult]
    errors: dict[str, str]


def process_many(paths: Iterable[str | Path], settings: Settings | None = None) -> BatchResult:
    """Process several files; one failing file never stops the others."""
    settings = settings or Settings.from_env()
    agent = build_agent(settings)
    batch = BatchResult({}, {})
    for path in paths:
        key = str(path)
        try:
            batch.results[key] = process_file(path, settings, agent)
        except IngestionError as exc:
            LOGGER.error("Skipping %s: %s", key, exc)
            batch.errors[key] = str(exc)
    return batch


def _safe_stem(source: str) -> str:
    """File-system safe name that keeps the extension, so a.txt and a.pdf do not collide."""
    name = re.sub(r"[^A-Za-z0-9_-]+", "_", Path(source).name.replace(".", "_"))
    return name.strip("_") or "document"


def write_outputs(result: ProcessingResult, output_dir: Path) -> tuple[Path, Path]:
    """Persist the JSON result and the Markdown report; return both paths."""
    reports = Path(output_dir) / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(result.document.source)
    json_path = reports / f"{stem}.json"
    md_path = reports / f"{stem}.md"
    json_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    md_path.write_text(result.report_markdown, encoding="utf-8")
    return json_path, md_path
