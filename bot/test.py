#!/usr/bin/env python3 -u
import os,sys,json,time
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append( os.getenv("CRYPTO_LIB","/projects/apps/shared/crypto") )

import cryptolib
from tradewallet import TradeWallet
from bittrexexchange import BittrexExchange
from datetime import datetime

wallet = TradeWallet({'market':"BTC-NXC",'budget': 0.005,'name':"NXC-TEST",'sync':True,'scale':8})
wallet.load()
wallet.exchange = BittrexExchange()

#b = wallet.buy(price=0.00000500,qty=280)
# print(json.dumps(b))
#r = wallet.exchange.cancel('8224d894-8625-45e0-89c2-93444b32c998')
#print(r)

#wallet.exchangeSync()
#trade = wallet.buys[2]
#wallet.sell(trade)

wallet.exchangeSync()
sig = wallet.getSignals()
print(json.dumps(sig))

#c = { "date":datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S') }
#b = wallet.buy(price=0.00000058,candle=c)
#print(b)

#r = wallet.exchange.api.market_get_open_orders("BTC-DOGE").getData()
#print( json.dumps(r))

#r = wallet.exchange.getOrderStatus("8224d894-8625-45e0-89c2-93444b32c998")
#print( json.dumps(r) )

#r = wallet.exchange.getOrderStatus("a78e51a9-7fab-45ad-9348-be1f93761c59")
#print( json.dumps(r) )
#c = { "date":datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S') }
#b = wallet.buy(price=0.00000058,candle=c)
#print(json.dumps(b))
#print(json.dumps(wallet.getSignals()))
