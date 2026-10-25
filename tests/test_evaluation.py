from __future__ import annotations

from pathlib import Path

import pytest

from idp_agent.config import Settings
from idp_agent.evaluation import evaluate_directory, prf
from idp_agent.samples import DOCUMENTS, EXPECTED, HARD_DOCUMENTS, HARD_EXPECTED


def test_prf_edge_cases() -> None:
    assert prf(0, 0, 0) == (1.0, 1.0, 1.0)
    assert prf(0, 2, 0) == (0.0, 0.0, 0.0)
    assert prf(2, 0, 2) == (1.0, 0.5, pytest.approx(2 / 3))


def test_every_sample_has_ground_truth() -> None:
    assert DOCUMENTS.keys() == EXPECTED.keys()
    assert HARD_DOCUMENTS.keys() == HARD_EXPECTED.keys()


def test_main_set_is_fully_correct(data_root: Path, settings: Settings) -> None:
    report = evaluate_directory(data_root / "samples", settings)
    assert len(report.scores) >= 5
    assert report.field_accuracy == 1.0
    assert report.measurement_prf[2] == 1.0
    assert report.severity_accuracy == 1.0 and report.action_accuracy == 1.0


def test_hard_set_exposes_known_limits(data_root: Path, settings: Settings) -> None:
    """Regression guard: the stress set must keep *measuring* failures, not hide them."""
    report = evaluate_directory(data_root / "samples_hard", settings)
    assert report.measurement_prf[1] < 1.0  # recall: tables / narrative values are missed
    assert report.measurement_prf[0] == 1.0  # but nothing is hallucinated
    assert "missed measurement" in report.format()
