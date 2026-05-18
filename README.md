# Dhan Trading Dashboard

A self-hosted trading dashboard for the [DhanHQ](https://dhanhq.co/) platform. Ships as a
single hardened Docker image that runs a FastAPI dashboard alongside JupyterLab for ad-hoc
market analysis — both gated behind a session-cookie login.

[![Docker Hub](https://img.shields.io/badge/Docker%20Hub-athcodes2005%2Fdhan--docker-2496ED?logo=docker)](https://hub.docker.com/r/athcodes2005/dhan-docker)
![Platform](https://img.shields.io/badge/platform-linux%2Farm64-lightgrey)
![Python](https://img.shields.io/badge/python-3.12-blue)

---

## Features

- **Portfolio overview** — fund limits, available margin, holdings with P&L, day's open positions, and a per-day NAV/invested history snapshot that the dashboard records as you visit the Account page.
- **Dhan API access-token management** — generate a fresh access token from your PIN + TOTP seed without ever copying credentials between sites; toggle auto-renewal so the dashboard's background loop refreshes the token within 5 minutes of expiry.
- **Static-IP whitelisting** — view the IP Dhan currently has on file, set a new primary IP, and gate the auto-renewal flow on it matching the VM's outbound address.
- **Data API status indicator** — a single probe call confirms whether your access token includes the Data API entitlement (Dhan error `DH-902` is mapped to a clear "not enabled" badge).
- **Instrument search** — fast prefix and substring search across the full NSE/BSE instrument list, kept in a local SQLite cache that the admin can refresh on demand.
- **JupyterLab** — full Python environment with `pandas`, `pandas-ta`, `numpy`, `matplotlib`, `plotly`, and `dhanhq` pre-installed. Reachable only via the dashboard's `forward_auth` gate, so guest sessions can't escape into a Python shell.

## Architecture

```
┌───────────────────────────── single Docker image ──────────────────────────────┐
│                                                                                │
│  ┌──────────────────────┐     ┌──────────────────────┐                         │
│  │  FastAPI dashboard   │     │  JupyterLab          │                         │
│  │  uvicorn :8000       │     │  lab --base_url=/lab │                         │
│  │  - session cookies   │     │  :8888               │                         │
│  │  - token renewal loop│     │  (no auth — gated    │                         │
│  │  - htmx partials     │     │   by reverse proxy)  │                         │
│  └─────────┬────────────┘     └──────────────────────┘                         │
│            │                                                                   │
│            └─────────────── supervisord (PID 1) ───────────────────────────────│
│                                                                                │
│   appuser (uid 999)  •  read-only rootfs  •  dropped caps  •  no-new-privs     │
│                                                                                │
│   /config ──── config.json          (Dhan access token, static IP, auto-renew) │
│   /app/data ── dhan_instruments.db  (NSE/BSE search index)                     │
│            └── portfolio_history.json                                          │
│   /app/notebooks                    (user JupyterLab notebooks)                │
└────────────────────────────────────────────────────────────────────────────────┘
```

The container is **not** intended to be reached directly from the public internet. The
provided `docker-compose.yml` binds both ports to `127.0.0.1` so you can put a reverse
proxy (Caddy, nginx, Traefik) in front. JupyterLab in particular must only be reached
through the dashboard's `forward_auth` subrequest gate (see [Reverse proxy](#reverse-proxy)).

## Quick start

### Option A — docker run

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

Dashboard: `http://localhost:8000`. Sign in as `admin` or `guest` with the passwords from `.env`.

### Option B — docker compose (recommended)

```bash
git clone https://github.com/athcodes2005/dhan-docker.git
cd dhan-docker
python generate_env.py        # interactive credential setup (writes .env with mode 600)
docker compose up -d
```

The bundled [`docker-compose.yml`](docker-compose.yml) applies every hardening flag for
you and creates three named volumes.

## Configuration

### Environment variables

Generate `.env` with `python generate_env.py` (verifies your TOTP seed live before
writing) or copy [`.env.example`](.env.example) and fill in the blanks.

| Variable | Required | Notes |
|----------|----------|-------|
| `DHAN_CLIENT_ID` | yes | Numeric client ID from your Dhan account |
| `DHAN_API_KEY` | yes | API key from the partner / data-api console |
| `DHAN_API_SECRET` | yes | Matching secret |
| `DHAN_PIN` | yes | 6-digit trading PIN — used during token generation |
| `DHAN_TOTP_SEED` | yes | Base32 TOTP seed; same one you scanned into your authenticator |
| `SECRET_KEY` | yes | Cookie signing key. `generate_env.py` creates one with `secrets.token_hex(32)`. **Rotate this and all sessions are invalidated.** |
| `ADMIN_PASSWORD` | yes | Dashboard admin password (full access) |
| `GUEST_PASSWORD` | yes | Dashboard guest password (read-only) |
| `TZ` | no | Defaults to `Asia/Kolkata` — affects supervisord log timestamps and the dashboard's day boundaries |

### Volumes

| Mount point | Purpose | Survives container recreate |
|-------------|---------|-----------------------------|
| `/config` | `config.json` — current access token, expiry, primary IP, `autoRenew` flag | yes, if mounted |
| `/app/data` | `dhan_instruments.db` (~45 MB), `portfolio_history.json` | yes |
| `/app/notebooks` | User-created `.ipynb` files | yes |

`config.json` is bootstrapped to `{}` by the entrypoint if missing — first run generates a
token via the dashboard's Authentication page and the file fills in.

### Ports

| Port | Service | Notes |
|------|---------|-------|
| `8000` | FastAPI dashboard | The only port `EXPOSE`d in the image |
| `8888` | JupyterLab (base_url `/lab/`) | **Not** `EXPOSE`d — reach only via a reverse-proxy gate |

## Login

| Username | Role | Capabilities |
|----------|------|--------------|
| `admin` | Admin | Everything: generate tokens, set static IP, refresh instruments DB, full JupyterLab |
| `guest` | Guest | Read-only: home, account, search — no token operations, no JupyterLab |

Both passwords come from `.env`. There is no signup or password-reset flow — change the
env var and restart the container.

## Reverse proxy

The dashboard publishes `GET /api/auth-check` specifically for reverse-proxy subrequest
auth: 200 for admin sessions, 401 for missing/expired session, 403 for non-admin. Use it
to gate `/lab/*` so JupyterLab can't be reached by guests or the unauthenticated.

### Caddy

```caddyfile
your-domain.example.com {
    encode zstd gzip
    header {
        Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        -Server
    }

    @lab path /lab/*
    handle @lab {
        forward_auth localhost:8000 {
            uri /api/auth-check
            copy_headers Cookie
            # FastAPI sees Upgrade/Connection headers and tries to serve the
            # GET as a WebSocket route, returning 403. Strip them.
            header_up -Upgrade
            header_up -Connection
        }
        reverse_proxy localhost:8888
    }

    handle {
        reverse_proxy localhost:8000
    }
}
```

### nginx

```nginx
location = /api/auth-check { proxy_pass http://127.0.0.1:8000; }

location /lab/ {
    auth_request /api/auth-check;
    error_page 401 = @login;

    proxy_pass http://127.0.0.1:8888;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

location @login { return 302 /login; }
location / { proxy_pass http://127.0.0.1:8000; }
```

## Operations

### Health check

The image declares a `HEALTHCHECK` that curls `http://localhost:8000/healthz` every 30
seconds. From the host:

```bash
docker inspect --format='{{.State.Health.Status}}' dhan-trading
```

### Logs

Supervisord forwards both `dashboard` and `jupyterlab` to stdout/stderr, so plain
`docker logs -f dhan-trading` shows everything. Each program is also restarted
automatically if it exits (supervisord `autorestart=true`).

### Pinning a specific version

Every push tags the short Git SHA in addition to `latest`. Pin against the SHA in
production to get reproducible deploys and an easy rollback target:

```bash
docker pull athcodes2005/dhan-docker:ee9f245
```

A full tag list is on [Docker Hub](https://hub.docker.com/r/athcodes2005/dhan-docker/tags).

### Updating

```bash
docker compose pull dhan
docker compose up -d
```

`pull_policy: always` is set in the production compose, so `up -d` alone also picks up
the latest `:latest`.

## Security

The image is hardened by default; the bundled compose file enables all of these:

- Non-root: every process runs as `appuser` (uid 999) via `gosu`. Only the entrypoint runs as root, just long enough to fix bind-mount ownership.
- Read-only root filesystem with `tmpfs` for `/tmp`, `/run`, `/home/appuser`. Persistent state lives only in the three named volumes.
- Capabilities dropped to `CHOWN`, `SETUID`, `SETGID`, `FOWNER`, `DAC_OVERRIDE` (the minimum supervisord needs to switch users).
- `no-new-privileges:true` — `setuid` binaries inside the container cannot elevate.
- Python deps locked via `uv.lock` and installed in a multi-stage build, so the runtime stage has no compiler or build tools.
- Base image pinned by digest, not floating `python:3.12-slim`.
- The Docker Hub access token is gitignored AND dockerignored — even an `ADD .` couldn't leak it.

## Building from source

```bash
git clone https://github.com/athcodes2005/dhan-docker.git
cd dhan-docker

# Local image
docker build -t dhan-docker:dev .

# Multi-arch push to a registry (the published image is linux/arm64)
SHA=$(git rev-parse --short HEAD)
docker buildx build --platform linux/arm64 \
  --tag athcodes2005/dhan-docker:latest \
  --tag athcodes2005/dhan-docker:$SHA \
  --push .
```

The image targets `linux/arm64` because the upstream deployment runs on a GCP C4A Axion
ARM VM. To run on `amd64` build it yourself with `--platform linux/amd64` — there are no
arch-specific dependencies.

## Development

```bash
uv sync                          # install dependencies into .venv
uv run python -m uvicorn app.main:app --reload --port 8000
# in another shell:
uv run jupyter lab --port 8888 --no-browser
```

`uv` is the project's package manager ([astral-sh/uv](https://github.com/astral-sh/uv));
the locked dependency tree is in [`uv.lock`](uv.lock).

### Project layout

```
app/
  main.py                # FastAPI app, AuthMiddleware, token renewal loop
  routes/
    auth.py              # /login, /logout
    home.py              # /, /api/fund-limits
    account.py           # /account, /api/holdings, /api/positions
    search.py            # /search, /api/search, /api/update-db
    token.py             # /authentication and the full token mgmt API
    lab.py               # /lab-page (the iframe host page)
  templates/             # Jinja2 templates + htmx partials
  static/                # style.css + favicon
authentication.py        # Dhan login wrapper, TOTP, access token persistence
instruments_search.py    # SQLite-backed NSE/BSE search
data_querying.py         # Helpers around dhanhq for the dashboard's read paths
generate_env.py          # Interactive .env builder with live TOTP verification
Dockerfile               # Two-stage build with uv + pinned digest
entrypoint.sh            # Volume chown, config.json bootstrap, SECRET_KEY fallback
supervisord.conf         # dashboard + jupyterlab process supervision
docker-compose.yml       # Local dev / hardened single-host run
```

## License

MIT — see image OCI labels.
