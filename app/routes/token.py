import os
import asyncio
from datetime import datetime

from fastapi import APIRouter, Request
from app.main import templates, load_config, get_sidebar_context
from authentication import (
    generate_new_access_token,
    get_whitelisted_ip,
    ensure_static_ip,
)

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

        ip_data = get_whitelisted_ip()
        if "error" in ip_data:
            ip_data = None

    return templates.TemplateResponse(request, "partials/token_status.html", {
        "user": request.state.user,
        "has_token": bool(config.get("accessToken")),
        "token": token_data,
        "ip": ip_data,
        "static_ip": os.getenv("STATIC_IP", ""),
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

    try:
        await asyncio.to_thread(generate_new_access_token)
        message = {"type": "success", "text": "Token generated successfully."}
    except Exception as e:
        message = {"type": "error", "text": f"Failed: {e}"}

    # Re-render full status after generation
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
                pass
        ip_data = get_whitelisted_ip()
        if "error" in ip_data:
            ip_data = None

    return templates.TemplateResponse(request, "partials/token_status.html", {
        "user": request.state.user,
        "has_token": bool(config.get("accessToken")),
        "token": token_data,
        "ip": ip_data,
        "static_ip": os.getenv("STATIC_IP", ""),
        "message": message,
    })


@router.post("/api/set-ip")
async def set_ip(request: Request):
    if request.state.user["role"] != "admin":
        return "<p class='error'>Admin access required.</p>"

    try:
        result = await asyncio.to_thread(ensure_static_ip)
        if result.get("ordersAllowed"):
            return "<p class='success'>Static IP registered successfully. Reload to see updated status.</p>"
        elif result.get("error"):
            return f"<p class='error'>Failed: {result['error']}</p>"
        else:
            return f"<p class='warning'>IP set but status unclear. Reload to check.</p>"
    except Exception as e:
        return f"<p class='error'>Error: {e}</p>"
