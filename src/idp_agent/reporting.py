"""Markdown report generation."""

from __future__ import annotations

from .models import ActionRecord, ExtractedDocument, Finding, Severity

_BADGE = {
    Severity.CRITICAL: "🔴 CRITICAL",
    Severity.WARNING: "🟠 WARNING",
    Severity.INFO: "🟢 OK",
}


def _cell(value: object) -> str:
    """Escape a value for use inside a Markdown table cell."""
    text = "—" if value in (None, "") else str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _table(headers: list[str], rows: list[list[object]]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    lines += ["| " + " | ".join(_cell(c) for c in row) + " |" for row in rows]
    return "\n".join(lines)


def overall_severity(findings: list[Finding]) -> Severity:
    if any(f.severity is Severity.CRITICAL for f in findings):
        return Severity.CRITICAL
    if any(f.severity is Severity.WARNING for f in findings):
        return Severity.WARNING
    return Severity.INFO


def render_report(
    doc: ExtractedDocument,
    findings: list[Finding],
    actions: list[ActionRecord],
    notes: list[str] | None = None,
) -> str:
    """Build a human-readable Markdown report for one processed document."""
    status = overall_severity(findings)
    counts = {s: sum(1 for f in findings if f.severity is s) for s in Severity}
    out: list[str] = [
        f"# Processing report — {doc.document_id or doc.source}",
        "",
        f"**Status:** {_BADGE[status]}  ",
        f"**Findings:** {counts[Severity.CRITICAL]} critical, "
        f"{counts[Severity.WARNING]} warning, {counts[Severity.INFO]} info  ",
        f"**Extraction confidence:** {doc.confidence:.0%}",
        "",
        "## Document",
        "",
        _table(
            ["Field", "Value"],
            [
                ["Source", doc.source],
                ["Title", doc.title],
                ["Type", doc.doc_type.value],
                ["Language", doc.language],
                ["Document ID", doc.document_id],
                ["Date", doc.document_date],
                ["Equipment", doc.equipment],
                ["Manufacturer", doc.manufacturer],
                ["Standards", ", ".join(doc.standards)],
            ],
        ),
        "",
        "## Extracted measurements",
        "",
    ]
    if doc.measurements:
        out.append(
            _table(
                ["Name", "Parameter", "Kind", "Value", "Unit"],
                [[m.name, m.parameter, m.kind, m.value, m.unit] for m in doc.measurements],
            )
        )
    else:
        out.append("_No measurement found._")

    out += ["", "## Verification findings", ""]
    if findings:
        out.append(
            _table(
                ["Severity", "Rule", "Message", "Evidence"],
                [[f.severity.value, f.rule, f.message, f.evidence] for f in findings],
            )
        )
    else:
        out.append("_All checks passed._")

    out += ["", "## Actions triggered by the agent", ""]
    if actions:
        out.append(
            _table(
                ["Tool", "Result", "Attempts", "OK"],
                [[a.tool, a.result, a.attempts, "yes" if a.ok else "NO"] for a in actions],
            )
        )
    else:
        out.append("_No action triggered._")

    if notes:
        out += ["", "## Agent notes", ""]
        out += [f"- {note}" for note in notes]
    return "\n".join(out) + "\n"
