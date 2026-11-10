# syntax=docker/dockerfile:1
#
# MecaTrack - production image (Flask + gunicorn, serves the API and the frontend).
#
#   docker build -t mecatrack .
#   docker run -p 8000:8000 --env-file .env mecatrack
#
# Two stages: everything needed to INSTALL dependencies stays in the builder;
# the runtime stage only receives the ready virtualenv and the source code.

ARG PYTHON_IMAGE=python:3.12-slim

# ---------- Stage 1: builder ----------
FROM ${PYTHON_IMAGE} AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# A virtualenv at a fixed path can be copied as a whole into the runtime stage
# (same base image, so the same interpreter path).
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# Only the requirements first: this layer is reused while they do not change,
# so editing the code does not reinstall every dependency.
COPY backend/requirements.txt /tmp/requirements.txt
# --only-binary: every dependency ships wheels, so no compiler is ever needed.
RUN pip install --only-binary=:all: -r /tmp/requirements.txt

# ---------- Stage 2: runtime ----------
FROM ${PYTHON_IMAGE} AS runtime

# Commit SHA passed by CI (--build-arg APP_VERSION=...); shown by GET /health.
ARG APP_VERSION=dev

LABEL org.opencontainers.image.title="MecaTrack" \
      org.opencontainers.image.description="Workshop appointments and vehicle tracking (Flask + PostgreSQL)" \
      org.opencontainers.image.source="https://github.com/Pablixsz/MecaTrack"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/opt/venv/bin:$PATH \
    FLASK_ENV=production \
    APP_VERSION=${APP_VERSION} \
    PORT=8000 \
    FRONTEND_DIR=/app/frontend \
    MARKET_DATA_DIR=/app/var/market_data

# Unprivileged user with a fixed UID (predictable file ownership in volumes).
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app/backend
# Code stays owned by root: the app user can read it but cannot modify it.
COPY backend/ ./
COPY frontend/ /app/frontend/
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh

# The only writable place: downloaded open-data snapshots (ephemeral, regenerable).
RUN mkdir -p /app/var/market_data && chown -R app:app /app/var

USER app

EXPOSE 8000

# No curl in the slim image: the interpreter is already there.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8000'), timeout=4)"]

ENTRYPOINT ["entrypoint.sh"]
# Settings (bind to $PORT, 1 worker x 4 threads, app factory) live in gunicorn.conf.py.
CMD ["gunicorn"]
