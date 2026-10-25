"""Typed data models shared by every stage of the pipeline."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class DocType(str, Enum):
    DATASHEET = "datasheet"
    MAINTENANCE_REPORT = "maintenance_report"
    INSPECTION_REPORT = "inspection_report"
    UNKNOWN = "unknown"


class Measurement(BaseModel):
    """A numeric value with a unit, optionally tied to a named parameter."""

    name: str
    parameter: str = "other"  # canonical: pressure, temperature, voltage, power, flow, vibration...
    value: float
    unit: str
    kind: str = "measured"  # measured | max | min | nominal
    source_text: str = ""


class Entity(BaseModel):
    text: str
    label: str  # STANDARD | ORG | PART_NUMBER | PERSON | DATE ...


class ExtractedDocument(BaseModel):
    """Structured information extracted from a single document."""

    source: str
    language: str = "en"
    doc_type: DocType = DocType.UNKNOWN
    title: str | None = None
    document_id: str | None = None
    document_date: date | None = None
    equipment: str | None = None
    manufacturer: str | None = None
    standards: list[str] = Field(default_factory=list)
    measurements: list[Measurement] = Field(default_factory=list)
    entities: list[Entity] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class Finding(BaseModel):
    """Result of a verification rule."""

    rule: str
    severity: Severity
    message: str
    evidence: str = ""


class ActionRecord(BaseModel):
    """An action triggered by the agent, with its outcome."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    ok: bool
    result: str
    attempts: int = 1


class ProcessingResult(BaseModel):
    document: ExtractedDocument
    findings: list[Finding] = Field(default_factory=list)
    actions: list[ActionRecord] = Field(default_factory=list)
    report_markdown: str = ""
    planner: str = "rules"
    notes: list[str] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def worst_severity(self) -> Severity:
        order = [Severity.INFO, Severity.WARNING, Severity.CRITICAL]
        if not self.findings:
            return Severity.INFO
        return max((f.severity for f in self.findings), key=order.index)
