from __future__ import annotations

from datetime import date

import pytest

from idp_agent.extraction import (
    classify_measurement,
    detect_language,
    extract_document,
    extract_issues,
    extract_measurements,
    extract_standards,
    parse_date,
)
from idp_agent.models import DocType


@pytest.mark.parametrize(
    ("line", "value", "unit", "parameter", "kind"),
    [
        ("- Maximum operating pressure: 16 bar", 16.0, "bar", "pressure", "max"),
        ("Pression mesurée : 11,5 bar", 11.5, "bar", "pressure", "measured"),
        ("Rated power: 7.5 kW", 7.5, "kW", "power", "nominal"),
        ("Motor temperature: 71 °C", 71.0, "°C", "temperature", "measured"),
        ("Température minimale: -20 °C", -20.0, "°C", "temperature", "min"),
        ("Vibration: 7.1 mm/s", 7.1, "mm/s", "vibration", "measured"),
    ],
)
def test_measurement_parsing(line: str, value: float, unit: str, parameter: str, kind: str) -> None:
    (m,) = extract_measurements(line)
    assert (m.value, m.unit, m.parameter, m.kind) == (value, unit, parameter, kind)


@pytest.mark.parametrize(
    "line",
    ["Date: 2026-03-12", "Equipment: Pump P-101", "Reference: 12 apples", "Observations: none"],
)
def test_non_measurements_are_ignored(line: str) -> None:
    assert extract_measurements(line) == []


def test_classify_measurement_defaults() -> None:
    assert classify_measurement("Something odd") == ("other", "measured")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2026-03-12", date(2026, 3, 12)),
        ("12/03/2026", date(2026, 3, 12)),
        ("12 March 2026", date(2026, 3, 12)),
        ("12 mars 2026", date(2026, 3, 12)),
        ("31/02/2026", None),
        ("soon", None),
    ],
)
def test_parse_date(text: str, expected: date | None) -> None:
    assert parse_date(text) == expected


def test_standards_are_normalised_and_deduplicated() -> None:
    text = "Complies with ISO 9906 and iso 9906? Also IEC 60034-1, EN 60204-1."
    assert extract_standards(text) == ["ISO 9906", "IEC 60034-1", "EN 60204-1"]


def test_issue_detection_skips_negations() -> None:
    text = "Observations: Leak detected at flange. No corrosion found. Aucune fissure détectée."
    assert extract_issues(text) == ["Leak detected at flange."]


def test_issue_label_is_stripped() -> None:
    (issue,) = extract_issues("Constats: Fuite d'huile au joint.")
    assert issue == "Fuite d'huile au joint."


def test_cannot_is_not_treated_as_negation() -> None:
    assert extract_issues("Pump cannot start: seal failure.") == [
        "Pump cannot start: seal failure."
    ]


def test_language_detection() -> None:
    assert detect_language("Le rapport de l'équipement est dans la pression") == "fr"
    assert detect_language("The report and the equipment are with the pressure") == "en"


def test_full_document_extraction() -> None:
    text = (
        "PUMP DATASHEET\nDocument ID: DS-1\nDate: 2026-01-05\nEquipment: Pump P-1\n"
        "Manufacturer: ACME\n- Maximum pressure: 10 bar\n"
    )
    doc = extract_document(text, source="x.txt")
    assert doc.doc_type is DocType.DATASHEET
    assert doc.title == "Pump datasheet"
    assert (doc.document_id, doc.document_date) == ("DS-1", date(2026, 1, 5))
    assert doc.manufacturer == "ACME"
    assert {e.label for e in doc.entities} == {"ORG"}
    assert doc.confidence == 1.0


def test_empty_text_gives_low_confidence() -> None:
    doc = extract_document("nothing useful here")
    assert doc.doc_type is DocType.UNKNOWN
    assert doc.confidence == 0.0
