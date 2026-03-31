import os
import re
import sys
import subprocess
import urllib.parse
import requests
import pyotp
import json
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright
from dhanhq import DhanLogin
load_dotenv()


def ensure_playwright_chrome():
    """Check if Playwright's Chromium is installed, and install it if not."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        print("✅ Playwright Chromium is already installed.")
    except Exception:
        print("⚠️  Playwright Chromium not found. Installing...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("✅ Playwright Chromium installed successfully.")


DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_PIN = os.getenv("DHAN_PIN")
DHAN_API_KEY = os.getenv("DHAN_API_KEY")
DHAN_API_SECRET = os.getenv("DHAN_API_SECRET")
DHAN_TOTP_SEED = os.getenv("DHAN_TOTP_SEED")
DHAN_MOBILE_NUMBER = os.getenv("DHAN_MOBILE_NUMBER")

dhan_login = DhanLogin(DHAN_CLIENT_ID)

user_data_dir = 'dhan-chrome'

def current_access_token():
    if not os.path.exists("config.json"):
        return None
    with open("config.json", "r") as f:
        data = json.load(f)
    return data.get('accessToken')


def generate_dhan_consent():
    url = f"https://auth.dhan.co/app/generate-consent?client_id={DHAN_CLIENT_ID}"
    headers = {'app_id': DHAN_API_KEY, 'app_secret': DHAN_API_SECRET}
    response = requests.post(url, headers=headers).json()
    if "consentAppId" not in response:
        print("❌ Consent ID generation failed.")
        print(response)
    else:
        return response.get("consentAppId")


def automate_dhan_login(consent_app_id):
    ensure_playwright_chrome()

    with sync_playwright() as p:
        print("🚀 Launching Chrome...")
        browser = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        try:
            # Construct Login URL
            login_url = f"https://auth.dhan.co/login/consentApp-login?consentAppId={consent_app_id}"
            print(f"🔗 Navigating to Login Page...")
            page.goto(login_url)

            # --- STEP A: Mobile Number ---
            print("📱 Entering Mobile Number...")
            mobile_input = page.get_by_placeholder(re.compile(r"Mobile|Number", re.I))
            mobile_input.fill(DHAN_MOBILE_NUMBER)
            page.click("button:has-text('Proceed'), #login-btn")
            page.wait_for_timeout(1000)

            # --- STEP B: TOTP (2FA) ---
            print("🔐 Entering TOTP...")
            page.wait_for_selector("input", state="visible")
            totp_code = pyotp.TOTP(DHAN_TOTP_SEED.replace(" ", "")).now()
            
            page.locator("input").first.click()
            page.keyboard.type(totp_code, delay=100)
            page.wait_for_timeout(1000)

            # --- STEP C: 6-Digit PIN + CAPTURE REDIRECT ---
            print("🔑 Entering PIN and watching for redirect...")
            page.wait_for_selector("input", state="visible")
            page.locator("input").first.click()

            # 🔥 THE FIX: Setup the listener BEFORE typing the PIN
            # This ensures we catch the request even if it happens instantly.
            try:
                with page.expect_request(
                    lambda req: "127.0.0.1" in req.url and "token" in req.url.lower(),
                    timeout=30000
                ) as request_info:
                    
                    # Trigger the action while the listener is active
                    page.keyboard.type(DHAN_PIN, delay=100)
                    print("⏳ PIN Typed. Waiting for network event...")

                # If we exit the 'with' block, it means the request was caught!
                request = request_info.value
                final_url = request.url
                print(f"✅ Captured URL: {final_url}")

                # --- STEP D: Extract Token ---
                parsed_url = urllib.parse.urlparse(final_url)
                query_params = urllib.parse.parse_qs(parsed_url.query)
                token_id = query_params.get('tokenid', [None])[0] or query_params.get('tokenId', [None])[0]

                if token_id:
                    print(f"🎉 Success! Extracted Token ID: {token_id}")
                    return token_id
                else:
                    print("❌ Redirect captured, but 'tokenid' missing.")
                    return None

            except Exception as e:
                print(f"❌ Failed to catch request (Timeout or Error): {e}")
                # Fallback: Check if the URL changed anyway
                if "127.0.0.1" in page.url:
                    print(f"⚠️ Fallback: Page URL is {page.url}")
                return None

        except Exception as e:
            print(f"❌ Automation Error: {e}")
            return None

        finally:
            print("🛑 Closing Browser...")
            browser.close()

def consume_dhan_consent(token_id):
    api_key = os.getenv("DHAN_API_KEY")
    api_secret = os.getenv("DHAN_API_SECRET")
    url = f"https://auth.dhan.co/app/consumeApp-consent?tokenId={token_id}"
    headers = {
        'app_id': api_key,
        'app_secret': api_secret
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        if "accessToken" in data:
            print("✅ Session data retrieved successfully.")
            return data
        else:
            print(f"❌ Unexpected response format: {data}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"❌ API Request Failed: {e}")
        return {"error": str(e)}

def generate_new_access_token():
    consent_id = generate_dhan_consent()
    if consent_id:
        token_id = automate_dhan_login(consent_id)
        if token_id:
            session_data = consume_dhan_consent(token_id)
            
            if session_data and "accessToken" in session_data:
                session_data["consent_id"] = consent_id
                session_data["token_id"] = token_id
                # Preserve autoRenew preference from existing config
                if os.path.exists("config.json"):
                    with open("config.json", "r") as f:
                        old_config = json.load(f)
                    if old_config.get("autoRenew"):
                        session_data["autoRenew"] = True
                print("✅ Access Token and Session Data successfully generated!")
                with open("config.json", "w") as f:
                    json.dump(session_data, f, indent=4)
                print("💾 Structure maintained and saved to config.json")
            else:
                print("❌ Failed to consume consent.")
        else:
            print("❌ Token ID not captured.")
    else:
        print("❌ Consent ID generation failed.")

def check_access_token():
    user_info = dhan_login.user_profile(current_access_token())
    print(user_info)


def get_whitelisted_ip():
    """Check the current whitelisted IP status on Dhan."""
    try:
        token = current_access_token()
        resp = requests.get(
            "https://api.dhan.co/v2/ip/getIP",
            headers={"Accept": "application/json", "Content-Type": "application/json", "access-token": token},
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def ensure_static_ip():
    """Check if STATIC_IP from .env is set as primary on Dhan. If not, register it."""
    static_ip = os.getenv("STATIC_IP")
    if not static_ip:
        return {"error": "STATIC_IP not set in .env"}

    ip_info = get_whitelisted_ip()
    if "error" in ip_info:
        return ip_info

    if ip_info.get("primaryIP") == static_ip:
        return ip_info

    # IP doesn't match — register it
    try:
        token = current_access_token()
        resp = requests.post(
            "https://api.dhan.co/v2/ip/setIP",
            headers={"Accept": "application/json", "Content-Type": "application/json", "access-token": token},
            json={"dhanClientId": DHAN_CLIENT_ID, "ip": static_ip, "ipFlag": "PRIMARY"},
        )
        result = resp.json()
        if isinstance(result, dict) and result.get("status") == "SUCCESS":
            return get_whitelisted_ip()
        return result
    except Exception as e:
        return {"error": str(e)}



if __name__ == "__main__":
    generate_new_access_token()