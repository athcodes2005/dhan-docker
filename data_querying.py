from dhanhq import MarketFeed,dhanhq,DhanContext
from authentication import current_access_token,DHAN_CLIENT_ID
import pandas as pd
import pandas_ta as ta
import numpy as np

dhan_context = DhanContext(DHAN_CLIENT_ID,current_access_token())
dhan = dhanhq(dhan_context)


#return open high low close volume timestamp
#def historical_daily_data(self, security_id, exchange_segment, instrument_type, from_date(yyyy-mm-dd), to_date, expiry_code=0, oi=False):  
#all values must be string 
#refer https://dhanhq.co/docs/v2/annexure/
#series obtained from instrument search 
def get_historical_data(security_id,exchange_segment,instrument_type,from_date,to_date):
    try:
        data = dhan.historical_daily_data(security_id,exchange_segment,instrument_type,from_date,to_date)
        raw_data =  data['data']
        print(raw_data)
        df = pd.DataFrame(raw_data)
        return df
    except Exception as e:
        print(e)


#intraday data can be fetched for 90 days at a time
def get_intraminute_data(security_id,exchange_segment,instrument_type,from_date,to_date):
    try:
        data = dhan.intraday_minute_data(security_id, exchange_segment, instrument_type, from_date, to_date)
        raw_data = data['data']
        df = pd.DataFrame(raw_data)
        return df
    except Exception as e:
        print(e)

