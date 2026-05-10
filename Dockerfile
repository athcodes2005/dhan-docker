# syntax=docker/dockerfile:1.7

# --- Build stage ---
FROM python:3.12-slim-bookworm@sha256:d193c6f51a7dbd10395d6328de3a7edb0516fb0608ca138036576f574c3e07d2 AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.12 /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# --- Runtime stage ---
FROM python:3.12-slim-bookworm@sha256:d193c6f51a7dbd10395d6328de3a7edb0516fb0608ca138036576f574c3e07d2

LABEL org.opencontainers.image.source="https://github.com/athcodes2005/dhan-python"
LABEL org.opencontainers.image.description="Dhan trading dashboard with FastAPI + JupyterLab"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.title="dhan-python"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:$PATH" \
    DATA_DIR=/app/data \
    CONFIG_PATH=/config/config.json \
    PYTHONPATH=/app

# Install only runtime system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor gosu curl && rm -rf /var/lib/apt/lists/*

RUN useradd -r -m -d /home/appuser -s /bin/sh appuser

WORKDIR /app

# Bring the locked virtualenv from the builder
COPY --from=builder /app/.venv /app/.venv

# Application code (note: generate_env.py is NOT shipped — it's a host-side tool)
COPY authentication.py instruments_search.py data_querying.py ./
COPY app/ app/

RUN mkdir -p /app/data /app/notebooks /config \
    && chown -R appuser:appuser /app /home/appuser

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000 8888

VOLUME ["/config", "/app/data", "/app/notebooks"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -fsS http://localhost:8000/healthz || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
