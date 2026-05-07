import os
import json
import asyncio
from datetime import datetime

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse
from app.main import templates, load_config, get_sidebar_context, get_dhan_client
from authentication import (
    generate_new_access_token,
    get_whitelisted_ip,
    ensure_static_ip,
    get_token_progress,
)


CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.json")


def _save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=4)

def _unwrap_ip(raw):
    if isinstance(raw, dict) and isinstance(raw.get("data"), dict):
        return raw["data"]
    return raw


def _check_data_api():
    try:
        dhan = get_dhan_client()
        if not dhan:
            return None
        resp = dhan.historical_daily_data("21428", "NSE_EQ", "EQUITY", "2025-01-01", "2025-01-02")
        if resp.get("status") == "failure":
            remarks = resp.get("remarks", {})
            code = remarks.get("error_code", "") if isinstance(remarks, dict) else ""
            if code == "DH-902":
                return False
        return True
    except Exception:
        return None

router = APIRouter()


@router.get("/authentication")
async def auth_page(request: Request):
    return templates.TemplateResponse(request, "authentication.html", {
        "active_page": "authentication",
        "user": request.state.user,
        **get_sidebar_context(),
    })


@router.get("/api/token-status")
async def token_status(request: Request):
    config = load_config()
    token_data = None
    ip_data = None

    if config.get("accessToken"):
        expiry_str = config.get("expiryTime")
        if expiry_str:
            try:
                expiry_dt = datetime.fromisoformat(expiry_str)
                now = datetime.now()
                time_left = expiry_dt - now
                total_secs = int(time_left.total_seconds())
                hours, remainder = divmod(max(total_secs, 0), 3600)
                minutes, _ = divmod(remainder, 60)
                token_data = {
                    "active": total_secs > 0,
                    "expiry": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "remaining": f"{hours}h {minutes}m",
                }
            except Exception:
                token_data = {"active": False, "expiry": "Parse error", "remaining": "0h 0m"}

        ip_data = _unwrap_ip(get_whitelisted_ip())
        if isinstance(ip_data, dict) and "error" in ip_data:
            ip_data = None
        data_api = _check_data_api()

    return templates.TemplateResponse(request, "partials/token_status.html", {
        "user": request.state.user,
        "has_token": bool(config.get("accessToken")),
        "token": token_data,
        "ip": ip_data,
        "data_api": data_api if config.get("accessToken") else None,
        "static_ip": os.getenv("STATIC_IP", ""),
        "auto_renew": config.get("autoRenew", False),
    })


@router.post("/api/toggle-auto-renew")
async def toggle_auto_renew(request: Request):
    if request.state.user["role"] != "admin":
        return templates.TemplateResponse(request, "partials/message.html", {
            "css_class": "error", "text": "Admin access required.",
        })

    config = load_config()
    config["autoRenew"] = not config.get("autoRenew", False)
    _save_config(config)

    # Re-render full token status
    token_data = None
    ip_data = None
    if config.get("accessToken"):
        expiry_str = config.get("expiryTime")
        if expiry_str:
            try:
                expiry_dt = datetime.fromisoformat(expiry_str)
                now = datetime.now()
                time_left = expiry_dt - now
                total_secs = int(time_left.total_seconds())
                hours, remainder = divmod(max(total_secs, 0), 3600)
                minutes, _ = divmod(remainder, 60)
                token_data = {
                    "active": total_secs > 0,
                    "expiry": expiry_dt.strftime("%Y-%m-%d %H:%M:%S"),
                    "remaining": f"{hours}h {minutes}m",
                }
            except Exception:
                pass
        ip_data = _unwrap_ip(get_whitelisted_ip())
        if isinstance(ip_data, dict) and "error" in ip_data:
            ip_data = None
        data_api = _check_data_api()

    state = "enabled" if config["autoRenew"] else "disabled"
    return templates.TemplateResponse(request, "partials/token_status.html", {
        "user": request.state.user,
        "has_token": bool(config.get("accessToken")),
        "token": token_data,
        "ip": ip_data,
        "data_api": data_api if config.get("accessToken") else None,
        "static_ip": os.getenv("STATIC_IP", ""),
        "auto_renew": config["autoRenew"],
        "message": {"type": "success", "text": f"Auto-renewal {state}."},
    })


@router.post("/api/generate-token")
async def generate_token(request: Request):
    if request.state.user["role"] != "admin":
        return templates.TemplateResponse(request, "partials/token_status.html", {
            "user": request.state.user,
            "has_token": False,
            "token": None,
            "ip": None,
            "static_ip": "",
            "message": {"type": "error", "text": "Admin access required."},
        })

    asyncio.get_event_loop().run_in_executor(None, generate_new_access_token)
    return templates.TemplateResponse(request, "partials/token_status.html", {
        "user": request.state.user,
        "has_token": False,
        "token": None,
        "ip": None,
        "static_ip": os.getenv("STATIC_IP", ""),
        "auto_renew": False,
        "generating": True,
    })


@router.get("/api/token-progress")
async def token_progress():
    async def event_stream():
        while True:
            progress = get_token_progress()
            data = json.dumps(progress)
            yield f"data: {data}\n\n"
            if progress["done"]:
                break
            await asyncio.sleep(0.5)
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/api/set-ip")
async def set_ip(request: Request):
    if request.state.user["role"] != "admin":
        return templates.TemplateResponse(request, "partials/message.html", {
            "css_class": "error", "text": "Admin access required.",
        })

    try:
        result = await asyncio.to_thread(ensure_static_ip)
        if result.get("ordersAllowed"):
            return templates.TemplateResponse(request, "partials/message.html", {
                "css_class": "success", "text": "Static IP registered successfully. Reload to see updated status.",
            })
        elif result.get("error"):
            return templates.TemplateResponse(request, "partials/message.html", {
                "css_class": "error", "text": f"Failed: {result['error']}",
            })
        else:
            return templates.TemplateResponse(request, "partials/message.html", {
                "css_class": "warning", "text": "IP set but status unclear. Reload to check.",
            })
    except Exception as e:
        return templates.TemplateResponse(request, "partials/message.html", {
            "css_class": "error", "text": f"Error: {e}",
        })
