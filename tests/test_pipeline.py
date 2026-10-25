from __future__ import annotations

import json
from pathlib import Path

from idp_agent.config import Settings
from idp_agent.models import Severity
from idp_agent.pipeline import process_file, process_many, process_text, write_outputs


def test_critical_document_end_to_end(samples_dir: Path, settings: Settings) -> None:
    result = process_file(samples_dir / "maintenance_report_critical_en.txt", settings)
    assert result.worst_severity is Severity.CRITICAL
    assert all(a.ok for a in result.actions)
    assert (settings.output_dir / "actions" / "tickets").is_dir()
    assert "Processing report" in result.report_markdown


def test_clean_document_triggers_only_archive(samples_dir: Path, settings: Settings) -> None:
    result = process_file(samples_dir / "datasheet_pump_en.txt", settings)
    assert result.findings == []
    assert [a.tool for a in result.actions] == ["archive_document"]


def test_process_text_uses_given_source(settings: Settings) -> None:
    result = process_text(
        "Maintenance report\nEquipment: P-1", source="mail.txt", settings=settings
    )
    assert result.document.source == "mail.txt"


def test_outputs_do_not_collide_between_formats(samples_dir: Path, settings: Settings) -> None:
    paths = [
        samples_dir / "maintenance_report_critical_en.txt",
        samples_dir / "maintenance_report_critical_en.pdf",
    ]
    batch = process_many(paths, settings)
    written = {write_outputs(r, settings.output_dir)[0].name for r in batch.results.values()}
    assert written == {
        "maintenance_report_critical_en_txt.json",
        "maintenance_report_critical_en_pdf.json",
    }
    data = json.loads((settings.output_dir / "reports" / sorted(written)[0]).read_text("utf-8"))
    assert data["document"]["document_id"] == "MR-2026-0142"


def test_one_bad_file_does_not_stop_the_batch(
    samples_dir: Path, settings: Settings, tmp_path: Path
) -> None:
    bad = tmp_path / "bad.xyz"
    bad.write_text("x")
    batch = process_many([bad, samples_dir / "datasheet_pump_en.txt"], settings)
    assert len(batch.results) == 1 and str(bad) in batch.errors
