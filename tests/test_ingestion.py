from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from idp_agent.ingestion import IngestionError, load_document


def test_text_file(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("  hello é  \n", encoding="utf-8")
    assert load_document(path) == "hello é"


def test_latin1_fallback(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes("pression mesurée".encode("latin-1"))
    assert load_document(path) == "pression mesurée"


@pytest.mark.parametrize(
    ("name", "content", "fragment"),
    [
        ("missing.txt", None, "not found"),
        ("a.xyz", "x", "Unsupported"),
        ("e.txt", "  \n", "No text"),
    ],
)
def test_errors(tmp_path: Path, name: str, content: str | None, fragment: str) -> None:
    path = tmp_path / name
    if content is not None:
        path.write_text(content, encoding="utf-8")
    with pytest.raises(IngestionError, match=fragment):
        load_document(path)


def test_pdf_text_layer(samples_dir: Path) -> None:
    text = load_document(samples_dir / "inspection_report_fr.pdf")
    assert "INS-2026-0207" in text and "11,5 bar" in text


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")
def test_image_ocr(samples_dir: Path) -> None:
    text = load_document(samples_dir / "maintenance_report_critical_en.png")
    assert "MR-2026-0142" in text and "18.2 bar" in text
