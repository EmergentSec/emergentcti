FROM ghcr.io/astral-sh/uv:latest AS uv

FROM python:3.12-slim AS builder

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* README.md ./
RUN uv sync --no-dev --no-install-project

COPY src/ src/
COPY alembic/ alembic/
COPY alembic.ini .
COPY assets/ assets/

RUN uv sync --no-dev

FROM python:3.12-slim AS production

RUN groupadd -g 1001 cti && \
    useradd -u 1001 -g cti -m -s /bin/bash cti

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/alembic /app/alembic
COPY --from=builder /app/alembic.ini /app/alembic.ini
COPY --from=builder /app/assets /app/assets

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

USER cti

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:8000/api/v1/health').raise_for_status()"

CMD ["gunicorn", "cti.main:app", "-w", "2", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8000", "--access-logfile", "-"]
