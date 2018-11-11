#!/usr/bin/env python3 -u
import os,sys,json,time
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append( os.getenv("CRYPTO_LIB","/projects/apps/shared/crypto") )

import cryptolib
from coinmarketcap import CoinMarketCap

cmc = CoinMarketCap()
k = cmc.topList()
print(k)
