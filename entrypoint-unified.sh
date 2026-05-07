#!/bin/sh
set -e

# Fix ownership of bind-mounted config directory
chown -R appuser:appuser /config /app/data /app/notebooks 2>/dev/null || true

# Create config.json if it doesn't exist
if [ ! -f /config/config.json ]; then
    echo '{}' > /config/config.json
    chown appuser:appuser /config/config.json
fi

# Generate Caddyfile
DOMAIN="${DOMAIN:-localhost}"
CADDYFILE="/etc/caddy/Caddyfile"

if [ "$DOMAIN" = "localhost" ]; then
    cat > "$CADDYFILE" <<CADDYEOF
:80 {
    handle /lab/* {
        reverse_proxy 127.0.0.1:8888
    }
    reverse_proxy 127.0.0.1:8000
}
CADDYEOF

elif [ -n "$DUCKDNS_TOKEN" ]; then
    cat > "$CADDYFILE" <<CADDYEOF
${DOMAIN} {
    tls {
        dns duckdns ${DUCKDNS_TOKEN}
    }

    header {
        Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Content-Security-Policy "default-src 'self'; script-src 'self' https://cdn.jsdelivr.net https://unpkg.com 'unsafe-inline' 'unsafe-eval'; style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' https://cdn.jsdelivr.net data:; connect-src 'self' wss://${DOMAIN}; frame-src 'self'"
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
        -Server
    }

    handle /lab/* {
        reverse_proxy 127.0.0.1:8888
    }

    reverse_proxy 127.0.0.1:8000
}
CADDYEOF

else
    cat > "$CADDYFILE" <<CADDYEOF
${DOMAIN} {
    header {
        Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=()"
        -Server
    }

    handle /lab/* {
        reverse_proxy 127.0.0.1:8888
    }

    reverse_proxy 127.0.0.1:8000
}
CADDYEOF
fi

# Generate SECRET_KEY if not set
if [ -z "$SECRET_KEY" ]; then
    export SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
    echo "WARNING: SECRET_KEY not set, generated ephemeral key (sessions won't survive restarts)"
fi

exec "$@"
