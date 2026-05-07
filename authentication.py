import os
import json
import threading
import pyotp
from dotenv import load_dotenv
from dhanhq import DhanLogin

load_dotenv()

DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_PIN = os.getenv("DHAN_PIN")
DHAN_API_KEY = os.getenv("DHAN_API_KEY")
DHAN_API_SECRET = os.getenv("DHAN_API_SECRET")
DHAN_TOTP_SEED = os.getenv("DHAN_TOTP_SEED")

CONFIG_PATH = os.environ.get("CONFIG_PATH", CONFIG_PATH)

dhan_login = DhanLogin(DHAN_CLIENT_ID)

_token_generation_lock = threading.Lock()
_progress = {"step": 0, "total": 3, "message": "", "done": False, "error": False}


def _set_progress(step, message, done=False, error=False):
    _progress["step"] = step
    _progress["message"] = message
    _progress["done"] = done
    _progress["error"] = error


def get_token_progress():
    return dict(_progress)


def current_access_token():
    if not os.path.exists(CONFIG_PATH):
        return None
    with open(CONFIG_PATH, "r") as f:
        data = json.load(f)
    return data.get("accessToken")


def _save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)


def _load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {}


def generate_new_access_token():
    if not _token_generation_lock.acquire(blocking=False):
        print("⚠️ Token generation already in progress, skipping.")
        return

    try:
        _set_progress(1, "Generating TOTP and calling Dhan API...")
        totp_code = pyotp.TOTP(DHAN_TOTP_SEED.replace(" ", "")).now()

        _set_progress(2, "Authenticating with PIN + TOTP...")
        response = dhan_login.generate_token(DHAN_PIN, totp_code)

        if response and response.get("accessToken"):
            old_config = _load_config()
            response["autoRenew"] = old_config.get("autoRenew", False)
            _save_config(response)
            print("✅ Access token generated successfully.")
            _set_progress(3, "Token generated successfully!", done=True)
        else:
            error_msg = response.get("errorMessage", "Unknown error") if response else "No response"
            print(f"❌ Token generation failed: {error_msg}")
            _set_progress(0, f"Failed: {error_msg}", done=True, error=True)

    except Exception as e:
        print(f"❌ Error: {e}")
        _set_progress(0, f"Error: {e}", done=True, error=True)
    finally:
        _token_generation_lock.release()


def renew_access_token():
    generate_new_access_token()


def get_whitelisted_ip():
    try:
        token = current_access_token()
        return dhan_login.get_ip(token)
    except Exception as e:
        return {"error": str(e)}


def ensure_static_ip():
    static_ip = os.getenv("STATIC_IP")
    if not static_ip:
        return {"error": "STATIC_IP not set in .env"}

    ip_info = get_whitelisted_ip()
    if "error" in ip_info:
        return ip_info

    if ip_info.get("primaryIP") == static_ip:
        return ip_info

    try:
        token = current_access_token()
        result = dhan_login.set_ip(token, static_ip, "PRIMARY")
        if isinstance(result, dict) and result.get("status") == "SUCCESS":
            return get_whitelisted_ip()
        return result
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    generate_new_access_token()
