from kiteconnect import KiteConnect
import os

api_key = os.environ.get("KITE_API_KEY", "tsm9w570sr8un8kj")
access_token = "taIvja5sheJNIjOUV2TWDNr1bFJNbtXt"

kite = KiteConnect(api_key=api_key)
kite.set_access_token(access_token)

instruments = kite.instruments("NSE")
defence = [i for i in instruments if "defence" in i['name'].lower() or "defense" in i['name'].lower() or "DEFENCE" in i['tradingsymbol'].upper()]

for d in defence:
    print(d['instrument_token'], d['tradingsymbol'], d['name'])
