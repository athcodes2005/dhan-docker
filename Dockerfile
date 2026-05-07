FROM python:3.12-slim-bookworm

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && \
    uv pip install --system --no-cache \
    "dhanhq>=2.2.0" "fastapi>=0.115.0" "itsdangerous>=2.2.0" \
    "jinja2>=3.1.0" "pandas>=2.3.3" \
    "pyotp>=2.9.0" "python-dotenv>=1.2.1" "python-multipart>=0.0.9" \
    "requests>=2.32.5" "tabulate>=0.9.0" "uvicorn[standard]>=0.30.0"

# Create non-root user
RUN useradd -r -m -d /home/appuser appuser

# Copy application code
COPY authentication.py generate_env.py \
     instruments_search.py data_querying.py account_details.py \
     .python-version ./
COPY app/ app/

# Fix ownership so appuser can write to app dir
RUN chown -R appuser:appuser /app /home/appuser

USER appuser

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
