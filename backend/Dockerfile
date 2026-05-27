# ExTaSy backend — production Docker image.
#
# Multi-stage build:
#   - builder: installs Python deps (no Tesseract noise)
#   - runtime: slim image + tesseract + language packs we actually use
#
# Image size ≈ 350 MB (most of which is the tesseract language packs).
# Boots in ≈ 2-3 seconds on a small VM.

# ─── Build stage ───────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# System deps needed to compile *some* wheels. Most of our deps ship binaries
# but psycopg may need libpq-dev at install time on certain platforms.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user -r requirements.txt

# ─── Runtime stage ─────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/app/.local/bin:$PATH

# tesseract + language packs. Order roughly by coverage so the layer cache
# benefits when we tweak the list. ENG is the baseline; everything else is
# what our parser actually exercises.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-rus \
        tesseract-ocr-srp \
        tesseract-ocr-srp-latn \
        tesseract-ocr-bos \
        tesseract-ocr-bul \
        tesseract-ocr-ukr \
        tesseract-ocr-deu \
        tesseract-ocr-fra \
        tesseract-ocr-spa \
        tesseract-ocr-ita \
        tesseract-ocr-tur \
        tesseract-ocr-ara \
        tesseract-ocr-chi-sim \
        tesseract-ocr-chi-tra \
        tesseract-ocr-jpn \
        tesseract-ocr-kor \
        tesseract-ocr-tha \
        tesseract-ocr-hin \
        tesseract-ocr-heb \
        tesseract-ocr-ell \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — required by Fly.io and good hygiene everywhere.
RUN useradd --create-home --shell /bin/bash app
USER app
WORKDIR /home/app

# Pull installed Python deps from the builder stage.
COPY --from=builder --chown=app:app /root/.local /home/app/.local

# App code last so source edits don't bust the deps layer.
COPY --chown=app:app app /home/app/app

# Upload dir — Fly.io volumes mount here for persistence across deploys.
RUN mkdir -p /home/app/storage/uploads

ENV UPLOAD_DIR=/home/app/storage/uploads \
    PYTHONPATH=/home/app

# Fly.io / Railway / Render all set $PORT. Default 8000 for local docker runs.
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -fs http://127.0.0.1:${PORT}/health || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
