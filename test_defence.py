from kiteconnect import KiteConnect
from datetime import datetime, timedelta

api_key = "tsm9w570sr8un8kj"
access_token = "taIvja5sheJNIjOUV2TWDNr1bFJNbtXt"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

to_date = datetime.now()
from_date = to_date - timedelta(days=30)

data = kite.historical_data(
    instrument_token=6385665,
    from_date=from_date,
    to_date=to_date,
    interval="15minute"
)
print(f"Total candles: {len(data)}")
print(f"First: {data[0]}")
print(f"Last: {data[-1]}")
