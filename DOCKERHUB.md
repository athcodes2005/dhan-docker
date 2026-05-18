# dhan-docker

Self-hosted trading dashboard for the [DhanHQ](https://dhanhq.co/) platform — a FastAPI
dashboard and a gated JupyterLab in one hardened image.

**Source:** https://github.com/athcodes2005/dhan-docker

---

## What's inside

| Service | Port | Description |
|---------|------|-------------|
| Dashboard | `8000` | Portfolio, holdings, positions, instruments search, Dhan access-token management with auto-renewal |
| JupyterLab | `8888` | Pre-installed `pandas`, `pandas-ta`, `numpy`, `matplotlib`, `plotly`, `dhanhq` — base_url `/lab/` |

Both services run under `supervisord` as `appuser` (uid 999). Only port `8000` is
`EXPOSE`d; JupyterLab is intended to be reached through a reverse-proxy gate that
authenticates against the dashboard's `/api/auth-check` endpoint.

## Supported tags

| Tag | What it is | Use it when |
|-----|-----------|-------------|
| `latest` | Most recent push from `main` | You want auto-updates and you're OK with the latest changes |
| `<git-sha>` (e.g. `ee9f245`) | Pinned to a specific commit | Production — pin and review before promoting |

**Platform:** `linux/arm64` only (the upstream deployment is a GCP C4A Axion ARM VM).
For `amd64`, build from source — there are no arch-specific dependencies.

## Quick start

```bash
docker run -d \
  --name dhan-trading \
  --restart unless-stopped \
  --read-only \
  --tmpfs /tmp --tmpfs /run --tmpfs /home/appuser:size=128m,mode=1777 \
  --cap-drop ALL \
  --cap-add CHOWN --cap-add SETUID --cap-add SETGID --cap-add FOWNER --cap-add DAC_OVERRIDE \
  --security-opt no-new-privileges:true \
  -p 127.0.0.1:8000:8000 \
  -p 127.0.0.1:8888:8888 \
  --env-file .env \
  -v dhan_config:/config \
  -v dhan_data:/app/data \
  -v dhan_notebooks:/app/notebooks \
  athcodes2005/dhan-docker:latest
```

Then visit `http://localhost:8000` and sign in as `admin` or `guest`. Ports are bound to
loopback by design — put a reverse proxy in front (see [Reverse proxy](#reverse-proxy)).

## Environment

Required:

```
DHAN_CLIENT_ID    # numeric Dhan client ID
DHAN_API_KEY      # API key
DHAN_API_SECRET   # API secret
DHAN_PIN          # 6-digit trading PIN
DHAN_TOTP_SEED    # Base32 TOTP seed
SECRET_KEY        # cookie signing — generate: python -c 'import secrets;print(secrets.token_hex(32))'
ADMIN_PASSWORD
GUEST_PASSWORD
```

Optional: `TZ` (default `Asia/Kolkata`).

Helper: `python generate_env.py` in the source repo walks you through these interactively
and verifies the TOTP seed live before writing the file.

## Volumes

| Path | Contents |
|------|----------|
| `/config` | `config.json` — current Dhan access token, expiry, primary IP, auto-renew flag (bootstrapped to `{}` on first run) |
| `/app/data` | `dhan_instruments.db` (~45 MB NSE/BSE search index) + `portfolio_history.json` |
| `/app/notebooks` | User JupyterLab notebooks |

Always mount these as named volumes so state survives recreate. Without `/config` mounted,
you re-enter TOTP after every restart.

## Reverse proxy

The dashboard exposes `GET /api/auth-check` for proxy subrequest auth: **200** for admin
sessions, **401** for missing/expired, **403** for non-admin. Use it to gate `/lab/*`.

Minimal Caddy example:

```caddyfile
your-domain.example.com {
    @lab path /lab/*
    handle @lab {
        forward_auth localhost:8000 {
            uri /api/auth-check
            copy_headers Cookie
            header_up -Upgrade
            header_up -Connection
        }
        reverse_proxy localhost:8888
    }
    handle { reverse_proxy localhost:8000 }
}
```

Full nginx and Caddy-with-DuckDNS-DNS-01 examples are in the
[GitHub README](https://github.com/athcodes2005/dhan-docker#reverse-proxy).

## Roles

| User | Capabilities |
|------|--------------|
| `admin` | Full access: generate tokens, set static IP, refresh instruments DB, JupyterLab |
| `guest` | Read-only: home, account, search |

## Health check

The image declares `HEALTHCHECK CMD curl -fsS http://localhost:8000/healthz` — check from
the host with `docker inspect --format='{{.State.Health.Status}}' dhan-trading`.

## Security

Hardened by default. The bundled `docker-compose.yml` in the source repo applies all of:

- Read-only root FS (with `tmpfs` for `/tmp`, `/run`, `/home/appuser`)
- `cap_drop: ALL` + the minimum 5 caps supervisord needs to switch users
- `no-new-privileges:true`, non-root `appuser` (uid 999)
- Base image pinned by digest, Python deps locked via `uv.lock`, multi-stage build with no compiler/build tools in the runtime stage

JupyterLab gives full Python access including the loaded Dhan access token — **do not
expose port 8888 to the public internet under any circumstances**. Always gate it through
the `/api/auth-check` `forward_auth` pattern shown above.

## Links

- **Source & full docs:** https://github.com/athcodes2005/dhan-docker
- **Issues:** https://github.com/athcodes2005/dhan-docker/issues
- **License:** MIT
