"""Verification rules applied to extracted documents.

Each rule is a small pure function returning a list of :class:`Finding`.
Add a rule by writing a function and appending it to ``DEFAULT_RULES``.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import date

from .models import DocType, ExtractedDocument, Finding, Measurement, Severity

Rule = Callable[[ExtractedDocument], list[Finding]]

# Plausible physical ranges per canonical parameter and unit (sanity check, not a limit).
PLAUSIBLE_RANGES: dict[tuple[str, str], tuple[float, float]] = {
    ("temperature", "°c"): (-90.0, 1500.0),
    ("pressure", "bar"): (0.0, 2000.0),
    ("voltage", "v"): (0.0, 1_000_000.0),
    ("power", "kw"): (0.0, 1_000_000.0),
    ("vibration", "mm/s"): (0.0, 200.0),
}

# Normalisation factors to a reference unit so max/measured can be compared.
UNIT_TO_REFERENCE: dict[str, tuple[str, float]] = {
    "mbar": ("bar", 0.001),
    "bar": ("bar", 1.0),
    "kpa": ("bar", 0.01),
    "mpa": ("bar", 10.0),
    "pa": ("bar", 1e-5),
    "psi": ("bar", 0.0689476),
    "v": ("v", 1.0),
    "kv": ("v", 1000.0),
    "w": ("w", 1.0),
    "kw": ("w", 1000.0),
    "mw": ("w", 1e6),
    "°c": ("°c", 1.0),
    "mm/s": ("mm/s", 1.0),
}


def _to_reference(m: Measurement) -> tuple[str, float] | None:
    ref = UNIT_TO_REFERENCE.get(m.unit.lower())
    if ref is None:
        return None
    return ref[0], m.value * ref[1]


def rule_required_fields(doc: ExtractedDocument) -> list[Finding]:
    findings: list[Finding] = []
    required = {
        "document_id": doc.document_id,
        "document_date": doc.document_date,
        "equipment": doc.equipment,
    }
    for name, value in required.items():
        if value is None:
            findings.append(
                Finding(
                    rule="required_fields",
                    severity=Severity.WARNING,
                    message=f"Missing required field: {name}",
                )
            )
    if doc.doc_type is DocType.UNKNOWN:
        findings.append(
            Finding(
                rule="required_fields",
                severity=Severity.WARNING,
                message="Document type could not be determined",
            )
        )
    return findings


def rule_date_sanity(doc: ExtractedDocument) -> list[Finding]:
    if doc.document_date is None:
        return []
    today = date.today()
    if doc.document_date > today:
        return [
            Finding(
                rule="date_sanity",
                severity=Severity.WARNING,
                message=f"Document date {doc.document_date} is in the future",
            )
        ]
    if doc.document_date.year < 1990:
        return [
            Finding(
                rule="date_sanity",
                severity=Severity.WARNING,
                message=f"Document date {doc.document_date} is implausibly old",
            )
        ]
    return []


def rule_plausible_ranges(doc: ExtractedDocument) -> list[Finding]:
    findings: list[Finding] = []
    for m in doc.measurements:
        bounds = PLAUSIBLE_RANGES.get((m.parameter, m.unit.lower()))
        if bounds and not bounds[0] <= m.value <= bounds[1]:
            findings.append(
                Finding(
                    rule="plausible_ranges",
                    severity=Severity.WARNING,
                    message=f"{m.name} = {m.value} {m.unit} is outside the plausible range "
                    f"{bounds[0]}–{bounds[1]} (possible OCR/extraction error)",
                    evidence=m.source_text,
                )
            )
    return findings


def _comparable(value: Measurement, limit: Measurement) -> tuple[float, float] | None:
    """Return (value, limit) in a common unit, or ``None`` if they cannot be compared."""
    if limit.parameter != value.parameter:
        return None
    v_ref, l_ref = _to_reference(value), _to_reference(limit)
    if v_ref is None or l_ref is None or v_ref[0] != l_ref[0]:
        return None
    return v_ref[1], l_ref[1]


def rule_limits(doc: ExtractedDocument) -> list[Finding]:
    """Compare measured values with max/min limits for the same parameter."""
    findings: list[Finding] = []
    known = [m for m in doc.measurements if m.parameter != "other"]
    measured = [m for m in known if m.kind == "measured"]
    for value in measured:
        for limit in (m for m in known if m.kind in ("max", "min")):
            pair = _comparable(value, limit)
            if pair is None:
                continue
            exceeds = limit.kind == "max" and pair[0] > pair[1]
            below = limit.kind == "min" and pair[0] < pair[1]
            if exceeds or below:
                verb = "exceeds" if exceeds else "is below"
                findings.append(
                    Finding(
                        rule="limits",
                        severity=Severity.CRITICAL,
                        message=f"{value.name} ({value.value} {value.unit}) {verb} "
                        f"{limit.name} ({limit.value} {limit.unit})",
                        evidence=f"{value.source_text} | {limit.source_text}",
                    )
                )
    return findings


def rule_issues(doc: ExtractedDocument) -> list[Finding]:
    return [
        Finding(
            rule="reported_issue",
            severity=Severity.WARNING,
            message="Anomaly reported in document",
            evidence=issue,
        )
        for issue in doc.issues
    ]


def rule_standards(doc: ExtractedDocument) -> list[Finding]:
    if doc.doc_type is DocType.DATASHEET and not doc.standards:
        return [
            Finding(
                rule="standards",
                severity=Severity.INFO,
                message="Datasheet cites no standard (ISO/IEC/EN...)",
            )
        ]
    return []


DEFAULT_RULES: tuple[Rule, ...] = (
    rule_required_fields,
    rule_date_sanity,
    rule_plausible_ranges,
    rule_limits,
    rule_issues,
    rule_standards,
)


def validate(doc: ExtractedDocument, rules: Iterable[Rule] = DEFAULT_RULES) -> list[Finding]:
    """Run every rule; a crashing rule yields a finding instead of aborting the run."""
    findings: list[Finding] = []
    for rule in rules:
        try:
            findings.extend(rule(doc))
        except Exception as exc:  # noqa: BLE001 - one bad rule must not stop verification
            findings.append(
                Finding(
                    rule=getattr(rule, "__name__", "rule"),
                    severity=Severity.WARNING,
                    message=f"Rule failed: {exc}",
                )
            )
    return findings
