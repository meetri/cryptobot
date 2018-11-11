import os,sys,time,datetime,numpy,numbers,json
from bot import Bot
from marketanalyzer import Analyzer
from exchange import Exchange
from doubleband import DoubleBand
from tradewallet import TradeWallet
from bittrex import Bittrex

class ScanBot(Bot):

    def __init__(self,config={},name="ScanBot" ):
        config["timeframe"] = "14d"
        Bot.__init__(self,name,config)


    def calculate_ta(self):
        ta = self.analyzer.ta
        dband = ta.dband(14,2,1.5)
        macd = ta.getmacd()
        self.tadata = {
            "short.sma": ta.getsma(metric='closed',period=50).data,
            "long.sma": ta.getsma(metric='closed',period=200).data,
            # "price.sma": ta.getsma(metric='closed',period=20).data,
            "volume.sma": ta.getsma(metric='volume',period=20).data,
            "rsi": ta.getrsi(period=14,overbought=70,oversold=30).data,
            # "ibband.top": dband.iband.data[0],
            # "ibband.mid": dband.iband.data[1],
            # "ibband.bottom": dband.iband.data[2],
            "bband.top": dband.oband.data[0],
            "bband.mid": dband.oband.data[1],
            "bband.bottom": dband.oband.data[2],
            "macd": macd.data[0],
            "macd.signal": macd.data[1],
            "macd.history": macd.data[2],
        }


    def process(self, options = {}):
        scrape = options.get("scrape",False)
        self.refresh(scrape=scrape)
        if self.tadata["short.sma"][-1] > self.tadata["long.sma"][-1]:
            trend = "bull"
        else:
            trend = "bear"

        lidx = self.lastidx()
        tlen = 0
        for idx in range(lidx-1,0,-1):
            t = "bear"
            if self.tadata["short.sma"][idx] > self.tadata["long.sma"][idx]:
                t = "bull"
            if t == trend:
                tlen += 1
            else:
                break


            bvol = self.csdata["basevolume"][-1]
            vol = self.csdata["volume"][-1]
            smavol = self.tadata["volume.sma"][-1]
            val = self.csdata["closed"][-1]
            mf = vol * val
            smamf = smavol * val


        return {
                "scanner": self.name,
                "market": self.market,
                "candlesize": self.candlesize,
                "mf": mf,
                "smamf": smamf,
                "vol": vol,
                'smavol':smavol,
                "bvol": bvol,
                "val": val,
                "last": self.last,
                "trend": trend,
                "trend.length": tlen,
                "candle": self.csdata["time"][-1],
                "rsi": self.tadata["rsi"][-1],
                "long.sma": self.tadata["long.sma"][-1],
                "short.sma": self.tadata["short.sma"][-1],
                "bband.width": self.tadata["bband.top"][-1]-self.tadata["bband.bottom"][-1],
                "bband.top": self.tadata["bband.top"][-1],
                "bband.mid": self.tadata["bband.mid"][-1],
                "bband.bottom": self.tadata["bband.top"][-1],
                "macd": self.tadata["macd"][-1],
                "macd.signal": self.tadata["macd.signal"][-1],
                "macd.history": self.tadata["macd.history"][-1],
                }

