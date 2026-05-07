# Dhan Python Trading Dashboard

A FastAPI-based trading dashboard for the [DhanHQ](https://dhanhq.co/) platform. Automates authentication via Playwright, displays portfolio data, and provides instrument search.

## Login Credentials

The dashboard supports two user roles:

| Username | Role | Permissions |
|----------|------|-------------|
| `admin` | Admin | Full access: generate tokens, set IP, update database |
| `guest` | Guest | View only: fund limits, holdings, positions, search |

Passwords are set in the `.env` file (`ADMIN_PASSWORD` and `GUEST_PASSWORD`). Run `python generate_env.py` to configure them.

## Dashboard Pages

- **Home** - Fund limits overview with real-time balance metrics
- **Authentication** - Token status, IP whitelisting status, token generation (admin only)
- **Account** - Holdings and positions tabs with live data
- **Search** - Instrument search across NSE/BSE with database update (admin only)

## Local Setup

```bash
# Create virtual environment
python3.12 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install uv
uv pip install -r pyproject.toml

# Install Playwright browser
python -m playwright install chromium

# Generate .env credentials file
python generate_env.py

# Run the dashboard
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

Create a `.env` file (or use `python generate_env.py`):

```
DHAN_CLIENT_ID=your_client_id
DHAN_API_KEY=your_api_key
DHAN_API_SECRET=your_api_secret
DHAN_PIN=your_trading_pin
DHAN_MOBILE_NUMBER=your_registered_mobile
DHAN_TOTP_SEED=your_totp_seed
ADMIN_PASSWORD=admin_dashboard_password
GUEST_PASSWORD=guest_dashboard_password
SECRET_KEY=your_secret_key
STATIC_IP=your_server_static_ip
```

## Deployment

The app is deployed on Google Cloud (project: `dhan-trading-server`) using Docker.

```bash
# Copy files to server
gcloud compute scp <files> trading-server:~/ --project=dhan-trading-server --zone=asia-south1-c

# SSH and rebuild containers
gcloud compute ssh trading-server --project=dhan-trading-server --zone=asia-south1-c \
  --command="docker compose up -d --build"
```

## Architecture

- **Container:** Docker with Xvfb for headless Playwright browser automation
- **Port:** 8000 (Uvicorn/FastAPI)
- **Static IP:** Configured via `STATIC_IP` in `.env`, whitelisted on Dhan for order execution
