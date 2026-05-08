#!/bin/sh
set -e

# Fix ownership of bind-mounted volumes
chown -R appuser:appuser /config /app/data /app/notebooks 2>/dev/null || true

# Create config.json if it doesn't exist
if [ ! -f /config/config.json ]; then
    echo '{}' > /config/config.json
    chown appuser:appuser /config/config.json
fi

# Generate SECRET_KEY if not set
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    echo "WARNING: SECRET_KEY not set, generated ephemeral key (sessions won't survive restarts)"
fi

exec "$@"
