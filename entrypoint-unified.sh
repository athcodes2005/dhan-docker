#!/bin/sh
set -e

# Fix ownership of bind-mounted config directory
chown -R appuser:appuser /config /app/data /app/notebooks 2>/dev/null || true

# Create config.json if it doesn't exist
if [ ! -f /config/config.json ]; then
    echo '{}' > /config/config.json
    chown appuser:appuser /config/config.json
fi

# Generate Caddyfile from template
DOMAIN="${DOMAIN:-localhost}"
CADDYFILE="/etc/caddy/Caddyfile"

if [ "$DOMAIN" = "localhost" ]; then
    # Local mode: HTTP only, no TLS
    sed -e "s|__DOMAIN__|:80|g" \
        -e "s|__TLS_BLOCK__||g" \
        /etc/caddy/Caddyfile.template > "$CADDYFILE"
elif [ -n "$DUCKDNS_TOKEN" ]; then
    # DuckDNS TLS mode
    TLS_BLOCK="tls { dns duckdns $DUCKDNS_TOKEN }"
    sed -e "s|__DOMAIN__|$DOMAIN|g" \
        -e "s|__TLS_BLOCK__|$TLS_BLOCK|g" \
        /etc/caddy/Caddyfile.template > "$CADDYFILE"
else
    # Auto TLS (Caddy default — requires ports 80/443 open)
    sed -e "s|__DOMAIN__|$DOMAIN|g" \
        -e "s|__TLS_BLOCK__||g" \
        /etc/caddy/Caddyfile.template > "$CADDYFILE"
fi

# Generate SECRET_KEY if not set
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    echo "WARNING: SECRET_KEY not set, generated ephemeral key (sessions won't survive restarts)"
fi

exec "$@"
