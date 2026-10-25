"""Synthetic technical documents with ground truth, for demos, tests and evaluation.

All documents are fictional. ``generate_samples`` writes them as .txt (all), .pdf and
.png (a few, to exercise PDF parsing and OCR) next to a ``<name>.expected.json`` file
holding the expected extraction and agent behaviour. A second, harder set documents the
known limits of the rule-based extractor.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DOCUMENTS: dict[str, str] = {
    "datasheet_pump_en": """PUMP DATASHEET
Document ID: DS-2026-0101
Date: 2026-02-10
Equipment: Centrifugal pump CP-200
Manufacturer: Hydroflow Industries
Standards: ISO 9906, IEC 60034-1

Specifications
- Maximum operating pressure: 16 bar
- Rated power: 7.5 kW
- Maximum temperature: 120 °C
- Rated voltage: 400 V
- Rated speed: 2900 rpm
- Flow: 45 m3/h
""",
    "maintenance_report_critical_en": """MAINTENANCE REPORT
Document ID: MR-2026-0142
Date: 2026-09-18
Equipment: Centrifugal pump CP-200
Technician: J. Moreau
Standards: ISO 13849-1

Measurements
- Measured pressure: 18.2 bar
- Maximum pressure: 16 bar
- Measured temperature: 96 °C
- Vibration: 7.1 mm/s

Observations: Leak detected at the discharge flange. Seal replaced; no corrosion found on the casing.
""",
    "inspection_report_fr": """RAPPORT D'INSPECTION
Référence: INS-2026-0207
Date: 12 octobre 2026
Équipement: Compresseur à vis CV-12
Fabricant: AirTech SA
Normes: ISO 1217, EN 60204-1
Inspecteur: A. Ben Salah

Mesures
- Pression mesurée : 11,5 bar
- Pression maximale : 13 bar
- Température mesurée : 88 °C
- Température maximale : 85 °C
- Vibration : 4,2 mm/s

Constats: Fuite d'huile constatée au niveau du joint d'arbre. Aucune fissure détectée.
""",
    "maintenance_incomplete_en": """Maintenance report
Equipment: Conveyor belt CB-7
Technician: S. Rossi

Measurements
- Motor current: 14.2 A
- Motor temperature: 71 °C

Observations: Abnormal noise from the drive roller.
""",
    "datasheet_suspect_values_en": """TRANSFORMER DATASHEET
Document ID: DS-2026-0388
Date: 2031-04-01
Equipment: Distribution transformer TR-630
Manufacturer: VoltEdge GmbH

Specifications
- Rated voltage: 20 kV
- Rated power: 500 kW
- Maximum temperature: 12000 °C
""",
}

# Which documents are also rendered as PDF / image (to exercise those ingestion paths).
PDF_DOCUMENTS = ("maintenance_report_critical_en", "inspection_report_fr")
IMAGE_DOCUMENTS = ("maintenance_report_critical_en",)

EXPECTED: dict[str, dict[str, Any]] = {
    "datasheet_pump_en": {
        "doc_type": "datasheet",
        "document_id": "DS-2026-0101",
        "document_date": "2026-02-10",
        "equipment": "Centrifugal pump CP-200",
        "standards": ["ISO 9906", "IEC 60034-1"],
        "measurements": [
            {"parameter": "pressure", "kind": "max", "value": 16.0, "unit": "bar"},
            {"parameter": "power", "kind": "nominal", "value": 7.5, "unit": "kW"},
            {"parameter": "temperature", "kind": "max", "value": 120.0, "unit": "°C"},
            {"parameter": "voltage", "kind": "nominal", "value": 400.0, "unit": "V"},
            {"parameter": "speed", "kind": "nominal", "value": 2900.0, "unit": "rpm"},
            {"parameter": "flow", "kind": "measured", "value": 45.0, "unit": "m3/h"},
        ],
        "worst_severity": "info",
        "actions": ["archive_document"],
    },
    "maintenance_report_critical_en": {
        "doc_type": "maintenance_report",
        "document_id": "MR-2026-0142",
        "document_date": "2026-09-18",
        "equipment": "Centrifugal pump CP-200",
        "standards": ["ISO 13849-1"],
        "measurements": [
            {"parameter": "pressure", "kind": "measured", "value": 18.2, "unit": "bar"},
            {"parameter": "pressure", "kind": "max", "value": 16.0, "unit": "bar"},
            {"parameter": "temperature", "kind": "measured", "value": 96.0, "unit": "°C"},
            {"parameter": "vibration", "kind": "measured", "value": 7.1, "unit": "mm/s"},
        ],
        "worst_severity": "critical",
        "actions": ["create_ticket", "send_alert", "request_human_review", "archive_document"],
    },
    "inspection_report_fr": {
        "doc_type": "inspection_report",
        "document_id": "INS-2026-0207",
        "document_date": "2026-10-12",
        "equipment": "Compresseur à vis CV-12",
        "standards": ["ISO 1217", "EN 60204-1"],
        "measurements": [
            {"parameter": "pressure", "kind": "measured", "value": 11.5, "unit": "bar"},
            {"parameter": "pressure", "kind": "max", "value": 13.0, "unit": "bar"},
            {"parameter": "temperature", "kind": "measured", "value": 88.0, "unit": "°C"},
            {"parameter": "temperature", "kind": "max", "value": 85.0, "unit": "°C"},
            {"parameter": "vibration", "kind": "measured", "value": 4.2, "unit": "mm/s"},
        ],
        "worst_severity": "critical",
        "actions": ["create_ticket", "send_alert", "request_human_review", "archive_document"],
    },
    "maintenance_incomplete_en": {
        "doc_type": "maintenance_report",
        "document_id": None,
        "document_date": None,
        "equipment": "Conveyor belt CB-7",
        "standards": [],
        "measurements": [
            {"parameter": "current", "kind": "measured", "value": 14.2, "unit": "A"},
            {"parameter": "temperature", "kind": "measured", "value": 71.0, "unit": "°C"},
        ],
        "worst_severity": "warning",
        "actions": ["request_human_review", "archive_document"],
    },
    "datasheet_suspect_values_en": {
        "doc_type": "datasheet",
        "document_id": "DS-2026-0388",
        "document_date": "2031-04-01",
        "equipment": "Distribution transformer TR-630",
        "standards": [],
        "measurements": [
            {"parameter": "voltage", "kind": "nominal", "value": 20.0, "unit": "kV"},
            {"parameter": "power", "kind": "nominal", "value": 500.0, "unit": "kW"},
            {"parameter": "temperature", "kind": "max", "value": 12000.0, "unit": "°C"},
        ],
        "worst_severity": "warning",
        "actions": ["request_human_review", "archive_document"],
    },
}

# A stress set: phrasing and layouts the rule-based extractor is *not* designed for.
# It documents known limitations honestly (see README, "Limitations").
HARD_DOCUMENTS: dict[str, str] = {
    "inspection_narrative_en": """SAFETY INSPECTION REPORT
Reference: SI-2026-0412
Date: 24/09/2026
Asset: Steam boiler B-3
Inspector: L. Dupont
Compliance: EN 12952-1

Operating pressure (max.): 10 bar
Pressure reading: 145 psi
During the round at 14:30 the technician noted a surface temperature of 135 °C near the burner.
Observations: Corrosion visible on the lower seam. Safety valve OK.
""",
    "maintenance_table_en": """MAINTENANCE REPORT
Document ID: WO-8841
Date: 2026-10-03
Equipment: Hydraulic press HP-9

Parameter      Value     Limit
Pressure       210 bar   200 bar
Temperature    64 °C     90 °C

Observations: Slight oil film under the cylinder.
""",
}

HARD_EXPECTED: dict[str, dict[str, Any]] = {
    "inspection_narrative_en": {
        "doc_type": "inspection_report",
        "document_id": "SI-2026-0412",
        "document_date": "2026-09-24",
        "equipment": "Steam boiler B-3",
        "standards": ["EN 12952-1"],
        "measurements": [
            {"parameter": "pressure", "kind": "max", "value": 10.0, "unit": "bar"},
            {"parameter": "pressure", "kind": "measured", "value": 145.0, "unit": "psi"},
            {"parameter": "temperature", "kind": "measured", "value": 135.0, "unit": "°C"},
        ],
        "worst_severity": "warning",
        "actions": ["request_human_review", "archive_document"],
    },
    "maintenance_table_en": {
        "doc_type": "maintenance_report",
        "document_id": "WO-8841",
        "document_date": "2026-10-03",
        "equipment": "Hydraulic press HP-9",
        "standards": [],
        "measurements": [
            {"parameter": "pressure", "kind": "measured", "value": 210.0, "unit": "bar"},
            {"parameter": "pressure", "kind": "max", "value": 200.0, "unit": "bar"},
            {"parameter": "temperature", "kind": "measured", "value": 64.0, "unit": "°C"},
            {"parameter": "temperature", "kind": "max", "value": 90.0, "unit": "°C"},
        ],
        "worst_severity": "critical",
        "actions": ["create_ticket", "send_alert", "request_human_review", "archive_document"],
    },
}


def _write_pdf(text: str, path: Path) -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path), pagesize=A4)
    _, height = A4
    pdf.setFont("Helvetica", 11)
    y = height - 60
    for line in text.splitlines():
        pdf.drawString(50, y, line)
        y -= 16
    pdf.save()


def _write_image(text: str, path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    font = ImageFont.load_default(size=26)
    lines = text.splitlines()
    line_height = 40
    image = Image.new("RGB", (1500, line_height * (len(lines) + 2)), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((40, 30 + i * line_height), line, fill="black", font=font)
    image.save(path)


def _write_set(
    directory: Path,
    documents: dict[str, str],
    expected: dict[str, dict[str, Any]],
    pdf: tuple[str, ...] = (),
    image: tuple[str, ...] = (),
) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, text in documents.items():
        txt = directory / f"{name}.txt"
        txt.write_text(text, encoding="utf-8")
        written.append(txt)
        (directory / f"{name}.expected.json").write_text(
            json.dumps(expected[name], indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        if name in pdf:
            _write_pdf(text, directory / f"{name}.pdf")
            written.append(directory / f"{name}.pdf")
        if name in image:
            _write_image(text, directory / f"{name}.png")
            written.append(directory / f"{name}.png")
    return written


def generate_samples(root: Path) -> list[Path]:
    """Write ``root/samples`` (main set) and ``root/samples_hard`` (stress set)."""
    root = Path(root)
    return [
        *_write_set(root / "samples", DOCUMENTS, EXPECTED, PDF_DOCUMENTS, IMAGE_DOCUMENTS),
        *_write_set(root / "samples_hard", HARD_DOCUMENTS, HARD_EXPECTED),
    ]
