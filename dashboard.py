import streamlit as st
import pandas as pd
import json
import os
from dotenv import load_dotenv
from dhanhq import DhanLogin, DhanContext, dhanhq
from authentication import (
    generate_new_access_token,
    current_access_token,
    get_whitelisted_ip,
    ensure_static_ip,
    DHAN_CLIENT_ID
)
from instruments_search import smart_search, update_database
from datetime import datetime

load_dotenv()

# Set page config
st.set_page_config(
    page_title="Dhan Python Dashboard",
    page_icon="📈",
    layout="wide"
)


# --- USER AUTHENTICATION ---
USERS = {
    "admin": {"password_env": "ADMIN_PASSWORD", "role": "admin"},
    "guest": {"password_env": "GUEST_PASSWORD", "role": "guest"},
}


def check_login():
    """Gate the dashboard behind username/password authentication."""
    # No passwords configured — allow access as admin (local dev)
    if not os.getenv("ADMIN_PASSWORD") and not os.getenv("GUEST_PASSWORD"):
        st.session_state["role"] = "admin"
        return True

    if st.session_state.get("authenticated"):
        return True

    st.title("🔒 Login")
    username = st.text_input("Username:")
    password = st.text_input("Password:", type="password")
    if st.button("Login", type="primary"):
        user = USERS.get(username)
        if user and password == os.getenv(user["password_env"], ""):
            st.session_state["authenticated"] = True
            st.session_state["role"] = user["role"]
            st.session_state["username"] = username
            st.rerun()
        else:
            st.error("Invalid username or password.")
    return False


def is_admin():
    return st.session_state.get("role") == "admin"


if not check_login():
    st.stop()

# --- HELPER FUNCTIONS ---
def get_dhan_client():
    """Initializes and returns the DhanHQ client if a valid token exists."""
    token = current_access_token()
    if token:
        try:
            dhan_context = DhanContext(DHAN_CLIENT_ID, token)
            return dhanhq(dhan_context)
        except Exception as e:
            st.error(f"Error initializing Dhan Client: {e}")
            return None
    return None

def load_config():
    if os.path.exists("config.json"):
        with open("config.json", "r") as f:
            return json.load(f)
    return {}

# --- SIDEBAR ---
with st.sidebar:
    st.title("Navigation")
    page = st.radio("Go to:", ["Home", "Authentication", "Account", "Search"])

    st.divider()
    role_label = st.session_state.get("username", "admin")
    if is_admin():
        st.info(f"Logged in as **{role_label}** (admin)")
    else:
        st.info(f"Logged in as **{role_label}** (view only)")

    st.divider()
    st.subheader("Status")
    config = load_config()
    if config.get("accessToken"):
        st.success("Token Present")
        ip_info = get_whitelisted_ip()
        if ip_info.get("ordersAllowed"):
            st.success("IP Matched — Orders Allowed")
        elif "error" in ip_info:
            st.warning("IP Check Failed")
        else:
            st.error("IP Mismatch — Orders Blocked")
    else:
        st.warning("No Token Found")

# --- PAGES ---

if page == "Home":
    st.title("📈 Dhan Python Dashboard")
    st.markdown("""
    Welcome to your Dhan trading dashboard. Use the sidebar to navigate.
    
    *   **Authentication**: Manage your access tokens.
    *   **Account**: View your holdings and positions.
    *   **Search**: Dictionary search for trading instruments.
    """)

    st.divider()
    st.subheader("📊 Fund Limits")
    
    dhan = get_dhan_client()
    if dhan:
        with st.spinner("Fetching fund limits..."):
            try:
                resp = dhan.get_fund_limits()
                if resp.get('status') == 'success':
                    data = resp.get('data', {})
                    
                    # exclude 'dhanClientId' from metrics 
                    metrics = {k: v for k, v in data.items() if k != 'dhanClientId'}
                    
                    # Create a grid of columns
                    cols = st.columns(4)
                    keys = list(metrics.keys())
                    
                    for i, key in enumerate(keys):
                        # Format key name: 'availabelBalance' -> 'Availabel Balance'
                        # Note: 'availabelBalance' seems to be a typo in API response key, we display it as is or fix it strictly if needed.
                        # Using simple string title case for generic approach
                        display_name = key.replace("([A-Z])", " \1").title()
                        
                        # Add Rupee symbol to values
                        val = f"₹{metrics[key]}"
                        
                        with cols[i % 4]:
                            st.metric(display_name, val)
                else:
                    st.error(f"Failed to fetch fund limits: {resp.get('remarks')}")
            except Exception as e:
                st.error(f"Error fetching fund limits: {e}")
    else:
        st.info("Please generate an access token in the Authentication tab to see fund limits.")

elif page == "Authentication":
    st.title("🔐 Authentication")
    
    st.info("Note: Generating a new token will launch a browser window on your machine.")
    
    config = load_config()
    
    # --- Token Status Display ---
    st.subheader("Token Status")
    
    if config.get("accessToken"):
        expiry_str = config.get("expiryTime")
        if expiry_str:
            try:
                # Handle ISO format. Config shows "2026-02-06T13:17:43"
                expiry_dt = datetime.fromisoformat(expiry_str)
                now = datetime.now()
                time_left = expiry_dt - now
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    if time_left.total_seconds() > 0:
                        st.metric("Status", "Active", delta="Valid")
                    else:
                        st.metric("Status", "Expired", delta="-Expired", delta_color="inverse")
                        
                with col2:
                    st.metric("Expiry Time", expiry_dt.strftime("%Y-%m-%d %H:%M:%S"))
                    
                with col3:
                    if time_left.total_seconds() > 0:
                        # Format time left nicely
                        hours, remainder = divmod(int(time_left.total_seconds()), 3600)
                        minutes, _ = divmod(remainder, 60)
                        st.metric("Time Remaining", f"{hours}h {minutes}m")
                    else:
                        st.metric("Time Remaining", "0h 0m")
            except Exception as e:
                st.error(f"Error parsing expiry time: {e}")
                st.write(f"Raw Expiry String: {expiry_str}")
        else:
            st.warning("Token present but no expiry time found.")
    else:
        st.error("No Access Token Found")

    st.divider()

    # --- IP Whitelisting Status ---
    st.subheader("IP Whitelisting")

    if config.get("accessToken"):
        ip_info = get_whitelisted_ip()
        if "error" not in ip_info:
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Primary IP", ip_info.get("primaryIP", "Not Set"))
                st.metric("Detected IP", ip_info.get("detectedIP", "Unknown"))
            with col2:
                match_status = ip_info.get("ipMatchStatus", "UNKNOWN")
                orders_allowed = ip_info.get("ordersAllowed", False)
                if orders_allowed:
                    st.metric("Match Status", match_status, delta="Orders Allowed")
                else:
                    st.metric("Match Status", match_status, delta="Orders Blocked", delta_color="inverse")
                st.metric("Can Change After", ip_info.get("modifyDatePrimary", "N/A"))

            if not orders_allowed:
                static_ip = os.getenv("STATIC_IP", "")
                if static_ip and is_admin():
                    if st.button("Set Static IP as Primary"):
                        with st.spinner(f"Registering {static_ip} as primary IP..."):
                            result = ensure_static_ip()
                            if result.get("ordersAllowed"):
                                st.success(f"IP {static_ip} registered successfully!")
                                st.rerun()
                            elif result.get("error"):
                                st.error(f"Failed: {result['error']}")
                            else:
                                st.warning(f"IP set but status: {result}")
                elif not static_ip:
                    st.warning("STATIC_IP not configured in .env")
        else:
            st.error(f"Failed to fetch IP status: {ip_info.get('error')}")
    else:
        st.info("Generate an access token first to view IP status.")

    st.divider()

    # --- Actions ---
    st.subheader("Actions")

    if is_admin():
        if st.button("Generate New Access Token", type="primary"):
            with st.spinner("Launching browser for login..."):
                try:
                    generate_new_access_token()
                    st.success("Token generation process completed. Check logs or Home status.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to generate token: {e}")
    else:
        st.info("Admin access required to generate tokens.")

elif page == "Account":
    st.title("💼 Account Summary")
    
    dhan = get_dhan_client()
    
    if not dhan:
        st.error("Please generate an access token in the Authentication tab first.")
    else:
        tab1, tab2 = st.tabs(["Holdings", "Positions"])
        
        with tab1:
            st.subheader("Holdings")
            with st.spinner("Fetching holdings..."):
                try:
                    resp = dhan.get_holdings()
                    if resp.get('status') == 'success':
                        data = resp.get('data', [])
                        if data:
                            df = pd.DataFrame(data)
                            st.dataframe(df, width="stretch")
                        else:
                            st.info("No holdings found.")
                    else:
                        st.error(f"Failed to fetch holdings: {resp.get('remarks')}")
                except Exception as e:
                    st.error(f"Error: {e}")

        with tab2:
            st.subheader("Positions")
            with st.spinner("Fetching positions..."):
                try:
                    resp = dhan.get_positions()
                    if resp.get('status') == 'success':
                        data = resp.get('data', [])
                        if data:
                            df = pd.DataFrame(data)
                            st.dataframe(df, width="stretch")
                        else:
                            st.info("No open positions.")
                    else:
                        st.error(f"Failed to fetch positions: {resp.get('remarks')}")
                except Exception as e:
                    st.error(f"Error: {e}")

elif page == "Search":
    st.title("🔍 Instrument Search")

    col1, col2 = st.columns([3, 1])
    with col1:
        query = st.text_input("Enter symbol name (e.g., TATA, VEDL):", "")
    with col2:
        st.write("") # Spacer
        st.write("") # Spacer
        if is_admin():
            if st.button("Update Database"):
                with st.spinner("Updating database (downloading CSV)..."):
                    try:
                        update_database()
                        st.success("Database updated successfully!")
                    except Exception as e:
                        st.error(f"Update failed: {e}")

    if query:
        with st.spinner("Searching..."):
            results = smart_search(query)
            
            if isinstance(results, list) and results:
                st.success(f"Found {len(results)} results")
                st.table(results)
            elif isinstance(results, list) and not results:
                st.warning("No results found.")
            else:
                st.error(f"Search error: {results}")

