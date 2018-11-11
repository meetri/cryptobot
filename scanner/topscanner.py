#!/usr/bin/env python3 -u

import os,sys,json,time,threading
sys.path.append( os.getenv("CRYPTO_LIB","/projects/apps/shared/crypto") )

import cryptolib
from influxdbwrapper import InfluxDbWrapper
from scanbot import ScanBot
from bittrex import Bittrex
from datetime import datetime
from mongowrapper import MongoWrapper
from cryptocompare import CryptoCompare
from concurrent.futures import ThreadPoolExecutor

bc = Bittrex()
cc = CryptoCompare()

def topscan( market ):
    print("{}".format(market))
    try:
        mongo = MongoWrapper.getInstance().getClient()
        bot = ScanBot({"market":market,"candlesize":"1d"},name='topscanner')
        res = bot.process({'scrape':True})
        mongo.crypto.scanner.replace_one({'market':market,'candlesize':'1d'},res,upsert=True)

        bot = ScanBot({"market":market,"candlesize":"1h"},name='topscanner')
        res = bot.process({'scrape':True})
        mongo.crypto.scanner.replace_one({'market':market,'candlesize':'1h'},res,upsert=True)

        bot = ScanBot({"market":market,"candlesize":"15m"},name='topscanner')
        res = bot.process({'scrape':True})
        mongo.crypto.scanner.replace_one({'market':market,'candlesize':'15m'},res,upsert=True)

        bot = ScanBot({"market":market,"candlesize":"5m"},name='topscanner')
        res = bot.process({'scrape':False})
        mongo.crypto.scanner.replace_one({'market':market,'candlesize':'5m'},res,upsert=True)
    except Exception as ex:
        print("Exception: {}".format(ex))


def scanner(max_threads=3):
    summaries = bc.public_get_market_summaries().data["result"]
    total = len(summaries)
    count = 0
    tasks = []

    marketList = []
    for summary in summaries:
        market = summary['MarketName']
        if not market.startswith("ETH"):
            marketList.append(market)

    with ThreadPoolExecutor(max_workers=max_threads) as executor:
        results = executor.map( topscan, marketList )




def main():
    loops = 0
    while True:
        try:
            scanner()
            print("{}:scan complete, sleeping for 1 minutes".format(loops))
            time.sleep(60)
            loops += 1
        except Exception as ex:
            print("Exception thrown: {}".format(ex))


if __name__ == "__main__":
    #mongo.crypto.drop_collection("scanner")
    main()

