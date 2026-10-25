from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from idp_agent.api import create_app  # noqa: E402
from idp_agent.config import Settings  # noqa: E402


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(Settings(output_dir=tmp_path, retry_backoff=0.0)))


def test_health(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["planner"] == "rules"


def test_upload_document(client: TestClient, samples_dir: Path) -> None:
    path = samples_dir / "maintenance_report_critical_en.txt"
    response = client.post("/process", files={"file": (path.name, path.read_bytes())})
    assert response.status_code == 200
    body = response.json()
    assert body["document"]["document_id"] == "MR-2026-0142"
    assert body["document"]["source"] == path.name


def test_process_text(client: TestClient) -> None:
    response = client.post("/process/text", json={"text": "Maintenance report\nEquipment: P-1"})
    assert response.status_code == 200


def test_rejects_unsupported_type(client: TestClient) -> None:
    response = client.post("/process", files={"file": ("evil.exe", b"MZ")})
    assert response.status_code == 415


def test_rejects_unreadable_document(client: TestClient) -> None:
    response = client.post("/process", files={"file": ("empty.txt", b"   ")})
    assert response.status_code == 422
