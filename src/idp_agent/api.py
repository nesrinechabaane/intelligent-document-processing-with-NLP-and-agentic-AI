"""FastAPI service exposing the pipeline over HTTP.

Run with ``idp serve`` or ``uvicorn idp_agent.api:app``. Endpoints are plain ``def``
functions so FastAPI runs the blocking work (OCR, parsing) in its thread pool.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from . import __version__
from .config import Settings
from .ingestion import SUPPORTED_SUFFIXES, IngestionError
from .models import ProcessingResult
from .pipeline import build_agent, process_file, process_text


class TextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=200_000)
    source: str = Field(default="api-text", max_length=120)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    agent = build_agent(settings)
    app = FastAPI(
        title="Intelligent Document Processing",
        version=__version__,
        description="Extract, verify and act on technical documents.",
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "planner": agent.planner_name}

    @app.post("/process/text", response_model=ProcessingResult)
    def process_raw_text(request: TextRequest) -> ProcessingResult:
        return process_text(request.text, request.source, settings, agent)

    @app.post("/process", response_model=ProcessingResult)
    def process_upload(file: UploadFile = File(...)) -> ProcessingResult:  # noqa: B008
        # Never trust the client filename for paths: keep only a validated suffix.
        original = Path(file.filename or "upload").name
        suffix = Path(original).suffix.lower()
        if suffix not in SUPPORTED_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{suffix}'. "
                f"Use one of {sorted(SUPPORTED_SUFFIXES)}.",
            )
        limit = settings.max_upload_mb * 1024 * 1024
        data = file.file.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(
                status_code=413, detail=f"File larger than {settings.max_upload_mb} MB"
            )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f"upload{suffix}"
            path.write_bytes(data)
            try:
                result = process_file(path, settings, agent, source=original)
            except IngestionError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result

    return app


app = create_app()
