import os
import json

from dhanhq import MarketFeed, dhanhq, DhanContext
import pandas as pd
import pandas_ta as ta
import numpy as np

CONFIG_PATH = os.environ.get("CONFIG_PATH", "config.json")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")


def _read_access_token():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f).get("accessToken")
    return None


def get_dhan():
    token = _read_access_token()
    if not token:
        raise RuntimeError("No access token found. Generate one from the dashboard first.")
    return dhanhq(DhanContext(DHAN_CLIENT_ID, token))


#return open high low close volume timestamp
#def historical_daily_data(self, security_id, exchange_segment, instrument_type, from_date(yyyy-mm-dd), to_date, expiry_code=0, oi=False):  
#all values must be string 
#refer https://dhanhq.co/docs/v2/annexure/
#series obtained from instrument search 
def get_historical_data(security_id, exchange_segment, instrument_type, from_date, to_date):
    try:
        dhan = get_dhan()
        data = dhan.historical_daily_data(security_id, exchange_segment, instrument_type, from_date, to_date)
        return pd.DataFrame(data["data"])
    except Exception as e:
        print(e)


def get_intraminute_data(security_id, exchange_segment, instrument_type, from_date, to_date):
    try:
        dhan = get_dhan()
        data = dhan.intraday_minute_data(security_id, exchange_segment, instrument_type, from_date, to_date)
        return pd.DataFrame(data["data"])
    except Exception as e:
        print(e)

