"""Measure extraction quality and agent behaviour against ground truth.

Ground truth lives next to each document in ``<stem>.expected.json`` (see
:mod:`idp_agent.samples`). The metrics are deliberately simple and transparent:

* **field accuracy** — exact match on type, id, date and equipment;
* **measurement P/R/F1** — a measurement is correct if (parameter, kind, value, unit) match;
* **standards P/R/F1** — set comparison on the cited standards;
* **severity accuracy** — the overall verdict equals the expected one;
* **action accuracy** — the set of tools executed successfully equals the expected set.
"""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .config import Settings
from .ingestion import SUPPORTED_SUFFIXES, IngestionError
from .models import ProcessingResult
from .pipeline import process_file
from .reporting import overall_severity

FIELDS = ("doc_type", "document_id", "document_date", "equipment")


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    """Precision, recall and F1 (1.0 when there is nothing to find and nothing found)."""
    if tp + fp + fn == 0:
        return 1.0, 1.0, 1.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


@dataclass
class FileScore:
    name: str
    error: str | None = None
    fields_correct: int = 0
    fields_total: int = len(FIELDS)
    measurements: tuple[int, int, int] = (0, 0, 0)  # tp, fp, fn
    standards: tuple[int, int, int] = (0, 0, 0)
    severity_ok: bool = False
    actions_ok: bool = False
    mismatches: list[str] = field(default_factory=list)


@dataclass
class EvaluationReport:
    scores: list[FileScore]

    @staticmethod
    def _sum(items: list[tuple[int, int, int]]) -> tuple[int, int, int]:
        return (sum(i[0] for i in items), sum(i[1] for i in items), sum(i[2] for i in items))

    @property
    def field_accuracy(self) -> float:
        total = sum(s.fields_total for s in self.scores)
        return sum(s.fields_correct for s in self.scores) / total if total else 0.0

    @property
    def measurement_prf(self) -> tuple[float, float, float]:
        return prf(*self._sum([s.measurements for s in self.scores]))

    @property
    def standards_prf(self) -> tuple[float, float, float]:
        return prf(*self._sum([s.standards for s in self.scores]))

    @property
    def severity_accuracy(self) -> float:
        return sum(s.severity_ok for s in self.scores) / len(self.scores) if self.scores else 0.0

    @property
    def action_accuracy(self) -> float:
        return sum(s.actions_ok for s in self.scores) / len(self.scores) if self.scores else 0.0

    def format(self) -> str:
        lines = [f"{'file':<46} fields  meas.F1  sev  actions"]
        for s in self.scores:
            if s.error:
                lines.append(f"{s.name:<46} ERROR: {s.error}")
                continue
            lines.append(
                f"{s.name:<46} {s.fields_correct}/{s.fields_total}     "
                f"{prf(*s.measurements)[2]:.2f}     {'ok ' if s.severity_ok else 'NO '}  "
                f"{'ok' if s.actions_ok else 'NO'}"
            )
            lines += [f"    - {m}" for m in s.mismatches]
        mp, mr, mf = self.measurement_prf
        sp, sr, sf = self.standards_prf
        lines += [
            "",
            f"Documents evaluated      : {len(self.scores)}",
            f"Field accuracy           : {self.field_accuracy:.1%}",
            f"Measurements P / R / F1  : {mp:.1%} / {mr:.1%} / {mf:.1%}",
            f"Standards    P / R / F1  : {sp:.1%} / {sr:.1%} / {sf:.1%}",
            f"Severity accuracy        : {self.severity_accuracy:.1%}",
            f"Action accuracy          : {self.action_accuracy:.1%}",
        ]
        return "\n".join(lines)


def _measurement_keys(items: list[dict[str, Any]]) -> Counter[tuple[str, str, float, str]]:
    return Counter(
        (m["parameter"], m["kind"], round(float(m["value"]), 3), str(m["unit"]).lower())
        for m in items
    )


def _compare(counter_pred: Counter, counter_true: Counter) -> tuple[int, int, int]:
    tp = sum((counter_pred & counter_true).values())
    return tp, sum(counter_pred.values()) - tp, sum(counter_true.values()) - tp


def score_result(name: str, result: ProcessingResult, expected: dict[str, Any]) -> FileScore:
    doc = result.document
    predicted_fields = {
        "doc_type": doc.doc_type.value,
        "document_id": doc.document_id,
        "document_date": doc.document_date.isoformat() if doc.document_date else None,
        "equipment": doc.equipment,
    }
    score = FileScore(name)
    for key in FIELDS:
        if predicted_fields[key] == expected.get(key):
            score.fields_correct += 1
        else:
            score.mismatches.append(
                f"{key}: got {predicted_fields[key]!r}, expected {expected.get(key)!r}"
            )

    predicted_meas = _measurement_keys([m.model_dump() for m in doc.measurements])
    expected_meas = _measurement_keys(expected.get("measurements", []))
    score.measurements = _compare(predicted_meas, expected_meas)
    for extra in predicted_meas - expected_meas:
        score.mismatches.append(f"unexpected measurement {extra}")
    for missed in expected_meas - predicted_meas:
        score.mismatches.append(f"missed measurement {missed}")

    predicted_std = Counter(s.upper() for s in doc.standards)
    expected_std = Counter(s.upper() for s in expected.get("standards", []))
    score.standards = _compare(predicted_std, expected_std)

    score.severity_ok = overall_severity(result.findings).value == expected.get("worst_severity")
    done = {a.tool for a in result.actions if a.ok}
    score.actions_ok = done == set(expected.get("actions", []))
    if not score.actions_ok:
        score.mismatches.append(
            f"actions: got {sorted(done)}, expected {sorted(expected.get('actions', []))}"
        )
    return score


def evaluate_directory(directory: Path, settings: Settings | None = None) -> EvaluationReport:
    """Process every document in ``directory`` that has an ``.expected.json`` sidecar."""
    directory = Path(directory)
    base = settings or Settings.from_env()
    scores: list[FileScore] = []
    with tempfile.TemporaryDirectory() as tmp:
        eval_settings = base.with_updates(output_dir=Path(tmp), llm_provider="none")
        for path in sorted(directory.iterdir()):
            if path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            sidecar = directory / f"{path.stem}.expected.json"
            if not sidecar.is_file():
                continue
            expected = json.loads(sidecar.read_text(encoding="utf-8"))
            try:
                result = process_file(path, eval_settings)
            except IngestionError as exc:
                scores.append(FileScore(path.name, error=str(exc)))
                continue
            scores.append(score_result(path.name, result, expected))
    return EvaluationReport(scores)
