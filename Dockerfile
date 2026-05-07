FROM python:3.12-slim-bookworm

# Install system dependencies for Playwright Chromium + Xvfb
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache \
    "dhanhq>=2.2.0" "fastapi>=0.115.0" "itsdangerous>=2.2.0" \
    "jinja2>=3.1.0" "pandas>=2.3.3" "playwright>=1.58.0" \
    "pyotp>=2.9.0" "python-dotenv>=1.2.1" "python-multipart>=0.0.9" \
    "requests>=2.32.5" "tabulate>=0.9.0" "uvicorn[standard]>=0.30.0"

# Create non-root user
RUN useradd -r -m -d /home/appuser appuser

# Install Playwright Chromium into shared location
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN python -m playwright install chromium && \
    chmod -R o+rx /opt/playwright-browsers

# Copy application code
COPY authentication.py generate_env.py \
     instruments_search.py data_querying.py account_details.py \
     .python-version ./
COPY app/ app/

# Fix ownership so appuser can write to app dir
RUN chown -R appuser:appuser /app /home/appuser

# Xvfb wrapper script
RUN printf '#!/bin/bash\nXvfb :99 -screen 0 1280x720x24 -nolisten tcp &\nexport DISPLAY=:99\nexec "$@"\n' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

USER appuser

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
