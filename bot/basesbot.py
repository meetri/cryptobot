import os,sys,time,datetime,numpy,numbers,json
from bot import Bot
from marketanalyzer import Analyzer
from exchange import Exchange
from doubleband import DoubleBand
from tradewallet import TradeWallet
from bittrex import Bittrex
from volumebases import VolumeBases

class BasesBot(Bot):

    def __init__(self,name="BasesBot",config={},settings=None):
        # config["timeframe"] = "7d"
        Bot.__init__(self,name,config,settings)

        self.bases = None
        self.sigevents = None
        self.pricecharts = None
        self.sim = None


    def setDefaults(self):
        self.defaults = {
                "baseMinDistance": 0.04,
                "baseMultiplier": 10,
                }

    def calculate_ta(self):
        ta = self.analyzer.ta
        self.tadata = {
            "volume.sma": ta.getsma(metric='volume',period=20).data,
            "rsi": ta.getrsi(period=14,overbought=70,oversold=30).data,
        }
        #self.bases = ta.getvolbases(self.tadata['volume.sma'],0.04,10).data
        self.bases = ta.getvolbases(self.tadata['volume.sma'],self.settings["baseMinDistance"],self.settings["baseMultiplier"]).data



    def handleSignals(self,wallet,price,signals, idx = None):

        # if there were any stop... sell
        sold = wallet.checkStops(candle=self.candle(idx),price=price, timeIndex=idx)

        if not sold:
            if signals['signal'] == 'buy':
                # buy something
                wallet.buy( price=price, signals=signals, timeIndex = idx, candle=self.candle(idx) )
            elif signals['signal'] == 'sell':
                # sell what's ready...
                wallet.checkSales(candle=self.candle(idx),price=price, timeIndex=idx)
            elif signals['signal'] == 'short':
                # sell everything ..
                wallet.short( price=price, signals=signals, timeIndex = idx, candle=self.candle(idx) )

        return wallet.getSignals()


    def process(self, options = {}):
        self.refresh(scrape=True)

        ta = self.analyzer.ta

        idx = self.lastidx()
        self.signals = self.getSignals( idx )
        self.sigevents = self.handleSignals( self.wallet,self.last,self.signals, idx )

        self.pricecharts = []
        for idx,t in enumerate( self.csdata["time"]):
            candle = self.candle(idx,ta=self.tadata)
            self.pricecharts.append(candle)

        self.buildOutput()


    def run_simulation(self,refresh=True):
        if refresh:
            self.refresh()

        self.simwallet.reset()

        simOn = "closed"
        for idx,t in enumerate( self.csdata["time"]):
            # self.bases = ta.getvolbases(self.tadata['volume.sma'],self.settings["baseMinDistance"],self.settings["baseMultiplier"]).data
            self.bases = VolumeBases(self.csdata,self.tadata["volume.sma"],{"md":self.settings["baseMinDistance"],"vmx":self.settings["baseMultiplier"]}).getBases(idx).data
            signals = self.getSignals(idx)
            self.handleSignals( self.simwallet,self.csdata["closed"][idx],signals, idx )

        self.sim = self.simwallet.getSignals()
        self.apiInfo["sim"] = json.dumps(self.sim)
        return self.simwallet


    def getPricePercentDif( self, price1, price2 ):
        return ((price1 - price2) * 100) / price1


    def baseSignals(self, idx, bases ):

        last = self.csdata["closed"][idx]

        scale = 70
        score = 0
        if bases is not None and len(bases) > 0:
            top = bases[0]["price"]
            bottom = bases[ len(bases)-1 ]["price"]
            height = top - bottom

            if last > top:
                score = -35
            elif last < bottom:
                score = 35
            elif height != 0:
                pd = last - bottom
                score = (pd * scale) / height
                score = self.score( score,idx, "({:.8f} * {:.8f}) / {:.8f} - top: {:.8f}, bottom: {:.8f}, height: {:.8f}, last: {:.8f}".format(pd,scale,height,top,bottom,height,last))
                score = (scale - score) - ( scale / 2 )
                #score = scale - ( abs(last-bottom) * (scale) / pd )

        return score


    def getSignals(self,idx):

        signal = ""
        score = 0

        if idx < 0:
            idx = len(self.csdata['volume'])+idx

        self.history = []

        score = self.baseSignals(idx,self.bases)

        if score >= 25:
            signal = 'buy'

        if score <= -25:
            signal = 'sell'

        if score <= -100:
            signal = 'short'

        return {
            'signal': signal,
            'score': score,
            'messages': self.history
        }


    def buildOutput(self):
        Bot.buildOutput(self)

        self.apiInfo["last"] = json.dumps({
                    "scraped": self.scrapeDate,
                    "candle": self.csdata["time"][-1],
                    "market":self.market,
                    "last":self.last
                })

        outta = {}
        for key in self.tadata:
            outta[key] = self.tadata[key][-1]

        self.apiInfo["ta"] = json.dumps(outta)

        self.apiInfo["signals"] = json.dumps(self.signals)
        self.apiInfo["bases"] = json.dumps(self.bases)
        self.apiInfo["events"] = json.dumps(self.sigevents)
        self.apiInfo["trades"] = json.dumps(self.wallet.getSignals())
        self.apiInfo["profit"] = json.dumps(self.wallet.getResults(self.last))
        self.apiInfo["simprofit"] = json.dumps(self.simwallet.getResults(self.last))
        self.apiInfo["charts"] = json.dumps({
            "summary": {
                "name": self.market,
                "scraped": self.scrapeDate,
                "candle": self.csdata["time"][-1],
                "candlesize": self.candlesize,
                "last": self.last,
                },
                "bases": self.bases,
                "signals": self.signals,
                "events": self.sigevents,
                "sim": self.simwallet.getSignals(),
                "sim.results": self.simwallet.getResults(self.last),
                "pricechart": self.pricecharts
            })
