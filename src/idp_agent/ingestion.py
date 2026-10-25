"""Document ingestion: turn files (txt, md, pdf, images) into plain text.

PDFs use the embedded text layer first; if it is empty (scanned PDF) the pages
are rendered and sent to OCR when ``pdf2image``/poppler are available.
Images go through Tesseract OCR.
"""

from __future__ import annotations

import logging
from pathlib import Path

LOGGER = logging.getLogger(__name__)

TEXT_SUFFIXES = {".txt", ".md", ".text"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}
PDF_SUFFIXES = {".pdf"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | IMAGE_SUFFIXES | PDF_SUFFIXES


class IngestionError(RuntimeError):
    """Raised when a document cannot be read."""


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "latin-1"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise IngestionError(f"Cannot decode {path}")


def ocr_image(path: Path, lang: str = "eng+fra") -> str:
    """Run Tesseract on an image. Falls back to English if a language pack is missing."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise IngestionError("OCR needs 'pytesseract' and 'pillow'") from exc

    try:
        with Image.open(path) as img:
            try:
                return pytesseract.image_to_string(img, lang=lang)
            except pytesseract.TesseractError:
                LOGGER.warning("OCR language pack '%s' unavailable, falling back to 'eng'", lang)
                return pytesseract.image_to_string(img, lang="eng")
    except pytesseract.TesseractNotFoundError as exc:
        raise IngestionError("Tesseract binary not found. Install it (see README).") from exc


def read_pdf(path: Path, ocr_lang: str = "eng+fra") -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [(page.extract_text() or "") for page in reader.pages]
    text = "\n".join(pages).strip()
    if text:
        return text

    LOGGER.info("No text layer in %s, trying OCR on rendered pages", path.name)
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError as exc:
        raise IngestionError(
            "Scanned PDF detected: install 'pdf2image' and poppler for OCR (see README)."
        ) from exc
    images = convert_from_path(str(path), dpi=200)
    return "\n".join(pytesseract.image_to_string(img, lang=ocr_lang) for img in images)


def load_document(path: str | Path, ocr_lang: str = "eng+fra") -> str:
    """Return the text content of ``path`` whatever its format."""
    p = Path(path)
    if not p.is_file():
        raise IngestionError(f"File not found: {p}")
    suffix = p.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        text = read_text_file(p)
    elif suffix in PDF_SUFFIXES:
        text = read_pdf(p, ocr_lang)
    elif suffix in IMAGE_SUFFIXES:
        text = ocr_image(p, ocr_lang)
    else:
        raise IngestionError(
            f"Unsupported file type '{suffix}'. Supported: {sorted(SUPPORTED_SUFFIXES)}"
        )
    text = text.strip()
    if not text:
        raise IngestionError(f"No text could be extracted from {p.name}")
    return text
