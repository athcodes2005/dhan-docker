from dhanhq import MarketFeed,dhanhq,DhanContext
from authentication import current_access_token,DHAN_CLIENT_ID

dhan_context = DhanContext(DHAN_CLIENT_ID,current_access_token())
dhan = dhanhq(dhan_context)




