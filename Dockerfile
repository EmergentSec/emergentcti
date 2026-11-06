# Pinned so builds are reproducible; bump deliberately alongside uv.lock changes.
FROM ghcr.io/astral-sh/uv:0.13.4 AS uv
FROM python:3.12-slim AS builder

COPY --from=uv /uv /usr/local/bin/uv
ENV UV_HTTP_TIMEOUT=120
WORKDIR /app

# uv.lock is required: --locked fails the build if it is missing or out of date
# with pyproject.toml, so images install exactly the audited dependency set.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
RUN uv sync --locked --no-dev

FROM python:3.12-slim AS production
RUN groupadd -g 1001 cti && useradd -u 1001 -g cti -m -s /bin/bash cti
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER cti
EXPOSE 8000

CMD ["gunicorn", "cti.main:app", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--access-logfile", "-"]
