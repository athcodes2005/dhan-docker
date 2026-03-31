import os
import json
from datetime import date

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from dhanhq import DhanContext, dhanhq

from authentication import current_access_token, DHAN_CLIENT_ID

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
COOKIE_MAX_AGE = 86400
USERS = {
    "admin": {"password_env": "ADMIN_PASSWORD", "role": "admin"},
    "guest": {"password_env": "GUEST_PASSWORD", "role": "guest"},
}

serializer = URLSafeTimedSerializer(SECRET_KEY)

templates = Jinja2Templates(directory="app/templates")

PORTFOLIO_HISTORY_FILE = "portfolio_history.json"


# --- Helpers ---

def get_dhan_client():
    token = current_access_token()
    if token:
        try:
            ctx = DhanContext(DHAN_CLIENT_ID, token)
            return dhanhq(ctx)
        except Exception:
            return None
    return None


def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            return json.load(f)
    return {}


def load_portfolio_history():
    if os.path.exists(PORTFOLIO_HISTORY_FILE):
        with open(PORTFOLIO_HISTORY_FILE, "r") as f:
            return json.load(f)
    return []


def save_portfolio_snapshot(invested, nav):
    history = load_portfolio_history()
    today = date.today().isoformat()
    for entry in history:
        if entry["date"] == today:
            entry["invested"] = invested
            entry["nav"] = nav
            break
    else:
        history.append({"date": today, "invested": invested, "nav": nav})
    with open(PORTFOLIO_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def get_sidebar_context():
    config = load_config()
    token_present = bool(config.get("accessToken"))
    ip_status = None
    if token_present:
        from authentication import get_whitelisted_ip
        ip_status = get_whitelisted_ip()
    return {"token_present": token_present, "ip_status": ip_status}


# --- Auth Middleware ---

class AuthMiddleware(BaseHTTPMiddleware):
    OPEN_PATHS = {"/login", "/static"}

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path == "/login" or path.startswith("/static"):
            return await call_next(request)

        cookie = request.cookies.get("session")
        if cookie:
            try:
                user = serializer.loads(cookie, max_age=COOKIE_MAX_AGE)
                request.state.user = user
                return await call_next(request)
            except (BadSignature, SignatureExpired):
                pass

        # No passwords configured — auto-login as admin (local dev)
        if not os.getenv("ADMIN_PASSWORD") and not os.getenv("GUEST_PASSWORD"):
            request.state.user = {"username": "admin", "role": "admin"}
            return await call_next(request)

        response = RedirectResponse("/login", status_code=302)
        response.delete_cookie("session")
        return response


# --- App ---

app = FastAPI(title="Dhan Trading Dashboard")
app.add_middleware(AuthMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

from app.routes import auth, home, token, account, search
app.include_router(auth.router)
app.include_router(home.router)
app.include_router(token.router)
app.include_router(account.router)
app.include_router(search.router)
