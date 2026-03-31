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
    uv pip install --system --no-cache --prerelease=allow -r pyproject.toml

# Install Playwright Chromium
RUN python -m playwright install chromium

# Copy application code
COPY authentication.py dashboard.py generate_env.py \
     instruments_search.py data_querying.py account_details.py \
     .python-version ./
COPY .streamlit/ .streamlit/

# Xvfb wrapper script
RUN printf '#!/bin/bash\nXvfb :99 -screen 0 1280x720x24 -nolisten tcp &\nexport DISPLAY=:99\nexec "$@"\n' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

EXPOSE 8501

ENTRYPOINT ["/entrypoint.sh"]
CMD ["streamlit", "run", "dashboard.py", "--server.port=8501", "--server.address=0.0.0.0"]
