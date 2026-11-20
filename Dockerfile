# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    FLASK_DEBUG=0

WORKDIR /app

# No extra OS packages: the health check below uses the Python stdlib.
RUN useradd --no-create-home --uid 10001 --shell /usr/sbin/nologin appuser

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code stays root-owned and read-only for the app user.
COPY . .

USER appuser
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8080'), timeout=4)" || exit 1

CMD gunicorn app:app \
  --bind 0.0.0.0:${PORT} \
  --workers ${WEB_CONCURRENCY:-2} \
  --threads ${WEB_THREADS:-4} \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --capture-output
