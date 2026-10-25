from __future__ import annotations

from datetime import date, timedelta

from idp_agent.models import DocType, ExtractedDocument, Measurement, Severity
from idp_agent.validation import validate


def _doc(**kwargs: object) -> ExtractedDocument:
    base: dict[str, object] = {
        "source": "t",
        "doc_type": DocType.MAINTENANCE_REPORT,
        "document_id": "A-1",
        "document_date": date(2026, 1, 1),
        "equipment": "Pump",
    }
    base.update(kwargs)
    return ExtractedDocument(**base)  # type: ignore[arg-type]


def _m(name: str, parameter: str, value: float, unit: str, kind: str) -> Measurement:
    return Measurement(name=name, parameter=parameter, value=value, unit=unit, kind=kind)


def _rules(findings: list) -> set[str]:
    return {f.rule for f in findings}


def test_clean_document_has_no_finding() -> None:
    assert validate(_doc()) == []


def test_missing_fields_are_warnings() -> None:
    findings = validate(_doc(document_id=None, equipment=None, doc_type=DocType.UNKNOWN))
    assert len(findings) == 3
    assert {f.severity for f in findings} == {Severity.WARNING}


def test_max_exceeded_is_critical() -> None:
    doc = _doc(
        measurements=[
            _m("Measured pressure", "pressure", 18.2, "bar", "measured"),
            _m("Max pressure", "pressure", 16, "bar", "max"),
        ]
    )
    (finding,) = validate(doc)
    assert finding.severity is Severity.CRITICAL and finding.rule == "limits"


def test_below_min_is_critical() -> None:
    doc = _doc(
        measurements=[
            _m("Voltage", "voltage", 190, "V", "measured"),
            _m("Min voltage", "voltage", 0.2, "kV", "min"),
        ]
    )
    assert [f.severity for f in validate(doc)] == [Severity.CRITICAL]


def test_units_are_converted_before_comparison() -> None:
    within = _doc(
        measurements=[
            _m("Pressure", "pressure", 145, "psi", "measured"),  # ~10.0 bar
            _m("Max pressure", "pressure", 10, "bar", "max"),
        ]
    )
    assert validate(within) == []
    exceeding = _doc(
        measurements=[
            _m("Pressure", "pressure", 1.2, "MPa", "measured"),  # 12 bar
            _m("Max pressure", "pressure", 10, "bar", "max"),
        ]
    )
    assert [f.severity for f in validate(exceeding)] == [Severity.CRITICAL]


def test_unknown_units_are_not_compared() -> None:
    doc = _doc(
        measurements=[
            _m("Flow", "flow", 99, "m3/h", "measured"),
            _m("Max flow", "flow", 10, "m3/h", "max"),
        ]
    )
    assert validate(doc) == []


def test_implausible_value_is_flagged_as_possible_extraction_error() -> None:
    doc = _doc(measurements=[_m("Temperature", "temperature", 12000, "°C", "measured")])
    assert _rules(validate(doc)) == {"plausible_ranges"}


def test_future_and_ancient_dates() -> None:
    future = _doc(document_date=date.today() + timedelta(days=30))
    ancient = _doc(document_date=date(1970, 1, 1))
    assert _rules(validate(future)) == {"date_sanity"}
    assert _rules(validate(ancient)) == {"date_sanity"}


def test_reported_issue_and_datasheet_without_standard() -> None:
    findings = validate(_doc(doc_type=DocType.DATASHEET, issues=["Leak at flange."]))
    assert _rules(findings) == {"reported_issue", "standards"}


def test_crashing_rule_does_not_abort_validation() -> None:
    def broken(_: ExtractedDocument) -> list:
        raise RuntimeError("boom")

    findings = validate(_doc(), rules=[broken])
    assert len(findings) == 1 and "boom" in findings[0].message
