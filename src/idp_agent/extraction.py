"""Rule-based structured extraction (bilingual EN/FR).

The extractor is deterministic and needs no model download, which makes it
testable and reproducible. Optional spaCy entities are added by
:mod:`idp_agent.entities`.
"""

from __future__ import annotations

import re
from datetime import date

from .models import DocType, Entity, ExtractedDocument, Measurement
from .vocabulary import (
    DOC_TYPE_KEYWORDS,
    ENGLISH_MARKERS,
    FIELD_LABELS,
    FRENCH_MARKERS,
    ISSUE_KEYWORDS,
    KIND_KEYWORDS,
    MONTHS,
    PARAMETER_KEYWORDS,
    UNITS,
)

_UNIT_PATTERN = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
_NUMBER = r"[-+]?\d+(?:[.,]\d+)?"
MEASUREMENT_RE = re.compile(
    rf"^\s*(?:[-•*]\s*)?(?P<name>[^:=\d][^:=]*?)\s*[:=]\s*(?P<value>{_NUMBER})\s*"
    rf"(?P<unit>{_UNIT_PATTERN})(?![A-Za-zµ°])",
    re.IGNORECASE,
)
STANDARD_RE = re.compile(r"\b(?:ISO|IEC|EN|DIN|ASTM|IEEE|NF|ANSI)\s?\d[\d]*(?:[-:/]\d+)*\b")
KEY_VALUE_RE = re.compile(r"^\s*(?:[-•*]\s*)?(?P<key>[^:\n]{2,40}?)\s*:\s*(?P<value>.+?)\s*$")
ISO_DATE_RE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
SLASH_DATE_RE = re.compile(r"\b(\d{1,2})[/.](\d{1,2})[/.](\d{4})\b")
TEXT_DATE_RE = re.compile(r"\b(\d{1,2})\s+([A-Za-zéûè]+)\s+(\d{4})\b")


def detect_language(text: str) -> str:
    lowered = f" {text.lower()} "
    fr = sum(lowered.count(m) for m in FRENCH_MARKERS)
    en = sum(lowered.count(m) for m in ENGLISH_MARKERS)
    return "fr" if fr > en else "en"


def detect_doc_type(text: str) -> DocType:
    head = text[:400].lower()
    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        if any(k in head for k in keywords):
            return doc_type
    lowered = text.lower()
    for doc_type, keywords in DOC_TYPE_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            return doc_type
    return DocType.UNKNOWN


def parse_date(value: str) -> date | None:
    """Parse ISO, dd/mm/yyyy and '12 March 2026' / '12 mars 2026' formats."""
    if m := ISO_DATE_RE.search(value):
        return _safe_date(int(m[1]), int(m[2]), int(m[3]))
    if m := SLASH_DATE_RE.search(value):
        return _safe_date(int(m[3]), int(m[2]), int(m[1]))
    if m := TEXT_DATE_RE.search(value):
        month = MONTHS.get(m[2].lower())
        if month:
            return _safe_date(int(m[3]), month, int(m[1]))
    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _field_for_label(label: str) -> str | None:
    cleaned = label.strip().lower()
    for field, aliases in FIELD_LABELS.items():
        if cleaned in aliases:
            return field
    return None


def classify_measurement(name: str) -> tuple[str, str]:
    """Return (canonical parameter, kind) for a measurement label."""
    lowered = name.lower()
    words = set(re.findall(r"[a-zéèàç]+", lowered))
    kind = "measured"
    for candidate, keywords in KIND_KEYWORDS.items():
        if any(k in words for k in keywords):
            kind = candidate
            break
    parameter = "other"
    for canonical, keywords in PARAMETER_KEYWORDS.items():
        if any(k in lowered for k in keywords):
            parameter = canonical
            break
    return parameter, kind


def extract_measurements(text: str) -> list[Measurement]:
    measurements: list[Measurement] = []
    for line in text.splitlines():
        match = MEASUREMENT_RE.match(line)
        if not match:
            continue
        name = match["name"].strip(" -•*")
        parameter, kind = classify_measurement(name)
        unit = match["unit"].replace("° ", "°")
        measurements.append(
            Measurement(
                name=name,
                parameter=parameter,
                value=float(match["value"].replace(",", ".")),
                unit=unit,
                kind=kind,
                source_text=line.strip(),
            )
        )
    return measurements


def extract_standards(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for m in STANDARD_RE.finditer(text):
        seen[re.sub(r"\s+", " ", m.group(0)).upper()] = None
    return list(seen)


def extract_issues(text: str) -> list[str]:
    """Return sentences/lines describing anomalies (keyword based)."""
    issues: list[str] = []
    for line in text.splitlines():
        stripped = line.strip(" -•*\t")
        if not stripped or MEASUREMENT_RE.match(line):
            continue
        labelled = KEY_VALUE_RE.match(line)
        if labelled and _field_for_label(labelled["key"]):
            stripped = labelled["value"]  # drop the "Observations:" label itself
        for sentence in re.split(r"(?<=[.!?])\s+", stripped):
            lowered = sentence.lower()
            if any(k in lowered for k in ISSUE_KEYWORDS) and _is_real_issue(lowered):
                clean = sentence.strip()
                if clean and clean not in issues:
                    issues.append(clean)
    return issues


_NEGATION_RE = re.compile(
    r"\b(?:no|not|without|none|aucune?|aucuns?|pas\s+de|sans|absence)\b", re.IGNORECASE
)


def _is_real_issue(lowered: str) -> bool:
    """Skip sentences that negate the anomaly ('no leak detected')."""
    return _NEGATION_RE.search(lowered) is None


def _first_title(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip(" #*")
        if stripped and ":" not in stripped:
            return stripped.capitalize() if stripped.isupper() else stripped
    return None


def extract_document(text: str, source: str = "<text>") -> ExtractedDocument:
    """Extract a structured :class:`ExtractedDocument` from raw text."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        if MEASUREMENT_RE.match(line):
            continue
        match = KEY_VALUE_RE.match(line)
        if not match:
            continue
        field = _field_for_label(match["key"])
        if field and field not in fields:
            fields[field] = match["value"].strip()

    document_date = parse_date(fields["document_date"]) if "document_date" in fields else None
    standards = extract_standards(text)
    measurements = extract_measurements(text)
    issues = extract_issues(text)

    entities: list[Entity] = [Entity(text=s, label="STANDARD") for s in standards]
    if manufacturer := fields.get("manufacturer"):
        entities.append(Entity(text=manufacturer, label="ORG"))
    if technician := fields.get("technician"):
        entities.append(Entity(text=technician, label="PERSON"))

    doc = ExtractedDocument(
        source=source,
        language=detect_language(text),
        doc_type=detect_doc_type(text),
        title=_first_title(text),
        document_id=fields.get("document_id"),
        document_date=document_date,
        equipment=fields.get("equipment"),
        manufacturer=fields.get("manufacturer"),
        standards=standards,
        measurements=measurements,
        entities=entities,
        issues=issues,
    )
    doc.confidence = estimate_confidence(doc)
    return doc


def estimate_confidence(doc: ExtractedDocument) -> float:
    """Share of expected fields that were found (0.0 - 1.0)."""
    checks = [
        doc.document_id is not None,
        doc.document_date is not None,
        doc.equipment is not None,
        doc.doc_type is not DocType.UNKNOWN,
        bool(doc.measurements),
    ]
    return round(sum(checks) / len(checks), 2)
