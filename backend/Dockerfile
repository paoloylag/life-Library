FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY migrations ./migrations
COPY alembic.ini entrypoint.sh ./

RUN pip install --upgrade pip && \
    pip install . && \
    addgroup --system library && \
    adduser --system --ingroup library library && \
    chown -R library:library /app && \
    chmod +x /app/entrypoint.sh

USER library

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

ENTRYPOINT ["/app/entrypoint.sh"]
