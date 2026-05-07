FROM caddy:2 AS caddy

FROM python:3.12-slim-bookworm

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor gosu curl && rm -rf /var/lib/apt/lists/*

# Copy stock Caddy binary (no plugins needed)
COPY --from=caddy /usr/bin/caddy /usr/bin/caddy

WORKDIR /app

# Install all Python dependencies (dashboard + lab)
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache \
    "dhanhq>=2.2.0" "fastapi>=0.115.0" "itsdangerous>=2.2.0" \
    "jinja2>=3.1.0" "pandas>=2.3.3" \
    "pyotp>=2.9.0" "python-dotenv>=1.2.1" "python-multipart>=0.0.9" \
    "requests>=2.32.5" "tabulate>=0.9.0" "uvicorn[standard]>=0.30.0" \
    "jupyterlab" "pandas-ta" "numpy" "matplotlib" "plotly"

# Create app user
RUN useradd -r -m -d /home/appuser -s /bin/sh appuser

# Copy application code
COPY authentication.py generate_env.py \
     instruments_search.py data_querying.py ./
COPY app/ app/

# Create directories for volumes
RUN mkdir -p /app/data /app/notebooks /config /etc/caddy \
    && chown -R appuser:appuser /app /home/appuser

# Copy config files
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV DATA_DIR=/app/data \
    CONFIG_PATH=/config/config.json \
    PYTHONPATH=/app

EXPOSE 80 443

VOLUME ["/config", "/app/data", "/app/notebooks"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
    CMD curl -f http://localhost:8000/ || exit 1

ENTRYPOINT ["/entrypoint.sh"]
CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
