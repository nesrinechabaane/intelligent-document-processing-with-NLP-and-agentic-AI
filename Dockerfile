FROM python:3.12-slim

# Tesseract (OCR) with English + French language packs, poppler for scanned PDFs
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       tesseract-ocr tesseract-ocr-eng tesseract-ocr-fra poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir ".[api,ocr-pdf]"

# Run as an unprivileged user; results are written to /data/output
RUN useradd --create-home appuser && mkdir -p /data/output && chown appuser /data/output
USER appuser
ENV IDP_OUTPUT_DIR=/data/output
VOLUME ["/data/output"]

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health')"
CMD ["uvicorn", "idp_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
