import streamlit as st
import pandas as pd
import json
import os
from dhanhq import DhanLogin, DhanContext, dhanhq
from authentication import (
    generate_new_access_token,
    current_access_token,
    DHAN_CLIENT_ID
)
from instruments_search import smart_search, update_database
from datetime import datetime

# Set page config
st.set_page_config(
    page_title="Dhan Python Dashboard",
    page_icon="📈",
    layout="wide"
)

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
    st.subheader("Status")
    config = load_config()
    if config.get("accessToken"):
        st.success("Token Present")
        # Could add expiry check here if expiryTime date string parsing was implemented
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
    
    # --- Actions ---
    st.subheader("Actions")
    
    if st.button("Generate New Access Token", type="primary"):
        with st.spinner("Launching browser for login..."):
            try:
                generate_new_access_token()
                st.success("Token generation process completed. Check logs or Home status.")
                st.rerun()
            except Exception as e:
                st.error(f"Failed to generate token: {e}")

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

