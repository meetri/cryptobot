import os,sys,time,datetime,numpy,numbers,json
from bot import Bot
from marketanalyzer import Analyzer
from exchange import Exchange
from doubleband import DoubleBand
from tradewallet import TradeWallet
from bittrex import Bittrex
from volumebases import VolumeBases

class TraderBot(Bot):

    def __init__(self,config={},name="TraderBot",settings=None):
        config["timeframe"] = "7d"
        Bot.__init__(self,name,config)

        self.apiInfo = {}

        self.history = []

        self.bases = None
        self.signals = None
        self.sigevents = None
        self.pricecharts = None
        self.sim = None



    def calculate_ta(self):
        ta = self.analyzer.ta
        dband = ta.dband(14,2,1.5)
        self.tadata = {
            "short.sma": ta.getsma(metric='closed',period=self.settings["short.sma.period"]).data,
            "long.sma": ta.getsma(metric='closed',period=self.settings["long.sma.period"]).data,
            "price.sma": ta.getsma(metric='closed',period=20).data,
            "volume.sma": ta.getsma(metric='volume',period=20).data,
            "volume.long.sma": ta.getsma(metric='volume',period=50).data,
            "rsi": ta.getrsi(period=14,overbought=70,oversold=30).data,
            "ibband.top": dband.iband.data[0],
            "ibband.mid": dband.iband.data[1],
            "ibband.bottom": dband.iband.data[2],
            "bband.top": dband.oband.data[0],
            "bband.mid": dband.oband.data[1],
            "bband.bottom": dband.oband.data[2]
        }
        #self.bases = ta.getvolbases(self.tadata['volume.sma'],0.04,10).data
        self.bases = ta.getvolbases(self.tadata['volume.sma'],self.settings["baseMinDistance"],self.settings["baseMultiplier"]).data


    def handleSignals(self,wallet,price,signals, idx = None):
        if signals['signal'] == 'buy':
            # buy something
            wallet.buy( price=price, signals=signals, timeIndex = idx, candle=self.candle(idx) )
        elif signals['signal'] == 'sell':
            # sell what's ready...
            wallet.checkSales(candle=self.candle(idx),price=price, timeIndex=idx)
        elif signals['signal'] == 'short':
            # sell everything ..
            wallet.short( price=price, signals=signals, timeIndex = idx, candle=self.candle(idx) )
        # else:
        #    self.wallet.report( self.candle(idx), signals=signals, timeIndex = idx )

        return wallet.getSignals()


    def process(self, options = {}):
        self.refresh(scrape=True)

        ta = self.analyzer.ta

        idx = self.lastidx()
        self.signals = self.getSignals( idx, self.tadata )
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
            signals = self.getSignals(idx, self.tadata )
            self.handleSignals( self.simwallet,self.csdata["closed"][idx],signals, idx )
            # self.handleSignals( self.simwallet,self.csdata["low"][idx],signals, idx )
            #self.handleSignals( self.simwallet,self.csdata["high"][idx],signals, idx )
            #self.handleSignals( self.simwallet,self.csdata["low"][idx],signals, idx )
            #self.handleSignals( self.simwallet,self.csdata[""][idx],signals, idx )



        self.sim = self.simwallet.getSignals()
        self.apiInfo["sim"] = json.dumps(self.sim)
        return self.simwallet



    def score( self, score, csdataIndex, message ):
        self.history.append({
            'candle': self.csdata['time'][csdataIndex],
            "score": score,
            "message": message
            })

        return score


    def getPricePercentDif( self, price1, price2 ):
        return ((price1 - price2) * 100) / price1

    def priceSignals(self, idx, tadata):
        score = 0


        if tadata['rsi'][idx] < self.settings["rsi.buy"]:
            score += self.score( 30, idx, "rsi is oversold @  " + str(tadata['rsi'][idx]))

        if tadata['rsi'][idx] > self.settings["rsi.sell"]:
            score += self.score( -30, idx, "rsi is overbought @  " + str(tadata['rsi'][idx]))

        if self.csdata['closed'][idx] <= tadata['short.sma'][idx]:
            score += self.score( 5, idx, "price is below the short sma")

        if self.csdata['closed'][idx] > tadata['short.sma'][idx]:
            score += self.score( 0, idx, "price is above the short sma")

        if self.csdata['closed'][idx] > tadata['long.sma'][idx]:
            score += self.score( 0, idx, "price is above the long sma")

        if self.csdata['closed'][idx] < tadata['long.sma'][idx]:
            score += self.score( 0, idx, "price is below the long sma")

        if tadata['short.sma'][idx] < tadata['long.sma'][idx]:
            score += self.score( self.settings["sma.bear.score"], idx, "the short sma is below the long sma (bearish)")

        if tadata['short.sma'][idx] > tadata['long.sma'][idx]:
            score += self.score( self.settings["sma.bull.score"], idx, "the short sma is above the long sma (bullish)")
            d = self.getPricePercentDif(tadata['short.sma'][idx],tadata['long.sma'][idx])
            score += self.score( 0, idx, "short/long sma {:.2f}% apart".format(d))



        if tadata['short.sma'][idx-1] > tadata['long.sma'][idx-1] and \
            tadata['short.sma'][idx] <= tadata['long.sma'][idx]:
            score += self.score( self.settings["death.cross"], idx, "death cross")


        if tadata['short.sma'][idx-1] < tadata['long.sma'][idx-1] and \
            tadata['short.sma'][idx] >= tadata['long.sma'][idx]:
            score += self.score( self.settings["golden.cross"], idx, "golden cross")


        if self.csdata['closed'][idx] > tadata['bband.bottom'][idx] and \
            self.csdata['closed'][idx] < tadata['ibband.bottom'][idx]:
            score += self.score( self.settings["dband.bottom"], idx, "price is between bottom double bollingband")


        if self.csdata['closed'][idx] < tadata['bband.top'][idx] and \
            self.csdata['closed'][idx] > tadata['ibband.top'][idx]:
            score += self.score( self.settings["dband.top"], idx, "price is between top double bollingband")


        if self.csdata['closed'][idx] > tadata['bband.bottom'][idx] and \
            self.csdata['closed'][idx] < tadata['bband.mid'][idx]:
            score += self.score( 0, idx, "price in lower bollingerband")


        if self.csdata['closed'][idx] > tadata['bband.mid'][idx] and \
            self.csdata['closed'][idx] < tadata['bband.top'][idx]:
            score += self.score( 0, idx, "price in upper bollingerband")


        if self.csdata['closed'][idx] < tadata['bband.bottom'][idx]:
            score += self.score( self.settings["bband.below"], idx, "price below bottom bollingerband")


        if self.csdata['closed'][idx] > tadata['bband.top'][idx]:
            score += self.score( self.settings["bband.above"], idx, "price above top bollingerband")


        if self.csdata['closed'][idx-1] < tadata['bband.bottom'][idx-1] and \
                self.csdata['closed'][idx] >= tadata['bband.bottom'][idx]:
            score += self.score( self.settings["bband.enter.bottom"], idx, "price moving up into the bottom bollingerband")

        '''

        if self.csdata['closed'][idx-1] > tadata['bband.mid'][idx-1] and \
                self.csdata['closed'][idx] < tadata['bband.mid'][idx]:
            score += self.score( 0, idx, "price crossing down the middle bollinger band")


        if self.csdata['closed'][idx-1] < tadata['bband.mid'][idx-1] and \
                self.csdata['closed'][idx] > tadata['bband.mid'][idx]:
            score += self.score( 0, idx, "price crossing above the middle bollinger band")


        if self.csdata['closed'][idx-1] > tadata['bband.bottom'][idx-1] and \
                self.csdata['closed'][idx] < tadata['bband.bottom'][idx]:
            score += self.score( 0, idx, "price crossing below  the bottom bollinger band")
        '''

        '''
        if self.csdata['closed'][idx-1] > tadata['bband.mid'][idx-1] and \
                self.csdata['closed'][idx] < tadata['bband.bottom'][idx]:
            score += self.score( -10, idx, "price spiking below  the bottom bollinger band")


        if self.csdata['closed'][idx-1] < tadata['bband.top'][idx-1] and \
                self.csdata['closed'][idx] > tadata['bband.top'][idx]:
            score += self.score( -10, idx, "price crossing above the top bollinger band")


        if self.csdata['open'][idx] > tadata['bband.top'][idx-1]and \
                self.csdata['closed'][idx] > tadata['bband.top'][idx]:
            score += self.score( -10, idx, "candle above top bollingband")


        if self.csdata['open'][idx] < tadata['bband.bottom'][idx] and \
                self.csdata['closed'][idx] < tadata['bband.bottom'][idx]:
            score += self.score( 0, idx, "candle below top bollingband")

        if self.candleColor(idx-1) == 'red' or self.candleColor(idx) == 'red':
            score += self.score( -10, idx, "previous candle was red.")

        '''


        '''
        if self.candleColor(idx-1) == 'green' and self.csdata['volume'][idx-1] > tadata['volume.sma'][idx]:
            # strengthen signal if price is moving up into the bottom band
            score += 0


        if self.candleColor(idx) == 'green' and self.csdata['volume'][idx] > tadata['volume.sma'][idx]:
            # previous strong green candle means more potential downward momentum
            score += 0


        if self.csdata['volume'][idx] < tadata['volume.sma'][idx]:
            # don't buy on high volume ( hard to tell if red or green and don't FOMO into anything )
            score += self.score( 5, idx, "volume is below the moving average")


        if numpy.isnan(tadata['volume.sma'][idx-1]):
            score = 0
        '''

        return score

    def volumeSignals(self, idx, tadata):
        score = 0
        if self.csdata['volume'][idx-1] > tadata['volume.sma'][idx-1]:
            mx = abs(self.csdata['volume'][idx-1] / tadata['volume.sma'][idx-1])
            if mx > 5:
                mx -= 5
                # score += self.score( -1 * 5 * abs(mx),idx-1, "previous candle's volume spiked above it's moving average")


        #TODO: may need to add volume prediction algorythm for current candle
        if self.csdata['volume'][idx] > tadata['volume.sma'][idx]:
            mx = self.csdata['volume'][idx] / tadata['volume.sma'][idx]
            if mx > 5:
                mx -= 5
                # score += self.score( -1 * 10 * abs(mx), idx, "volume is greater than moving average")

        return score


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


        #print("idx = {} score = {}".format(idx,score))

        return score



    def updateSettings(self,override = None):
        defaults = {
                "rsi.buy": 35,
                "rsi.sell": 65,
                "baseMinDistance": 0.04,
                "baseMultiplier": 10,
                "short.sma.period": 50,
                "long.sma.period": 200,
                "sma.bear.score": -25,
                "sma.bull.score": 5,
                "death.cross": -100,
                "golden.cross": 20,
                "dband.top": -15,
                "dband.bottom": 15,
                "bband.below": 5,
                "bband.above": -15,
                "bband.enter.bottom": 10,
                }

        if override != None:
            self.settings = {**defaults,**override}
        else:
            self.settings = defaults

        return self.settings


    def getSignals(self,idx, tadata):

        signal = ""
        score = 0

        if idx < 0:
            idx = len(self.csdata['volume'])+idx

        self.history = []

        '''
        if tadata['rsi'][idx] < self.settings["rsi.buy"]:
            score += self.score( 30, idx, "rsi is oversold @  " + str(tadata['rsi'][idx]))


        if tadata['rsi'][idx] > self.settings["rsi.sell"]:
            score += self.score( -30, idx, "rsi is overbought @  " + str(tadata['rsi'][idx]))

        if tadata['short.sma'][idx-1] > tadata['long.sma'][idx-1] and \
            tadata['short.sma'][idx] <= tadata['long.sma'][idx]:
            score += self.score( -30, idx, "death cross")


        if tadata['short.sma'][idx-1] < tadata['long.sma'][idx-1] and \
            tadata['short.sma'][idx] >= tadata['long.sma'][idx]:
            score += self.score( 30, idx, "golden cross")
        '''

        score += self.priceSignals(idx,tadata)
        score += self.volumeSignals(idx,tadata)
        #score = self.baseSignals(idx,self.bases)



        if score >= 35:
            signal = 'buy'

        if score <= -35:
            signal = 'sell'

        if score <= -100:
            signal = 'short'

        return {
            'signal': signal,
            'score': score,
            'messages': self.history
        }



    def getInfo(self, query=None):
        if query in self.apiInfo:
            return self.apiInfo[query]
        elif query == "stop":
            self.stopped = True
            return json.dumps({ "message": "bot stopped" })
        elif query == "debug":
            return json.dumps({
                    "scrapeDate": self.scrapeDate,
                    "market": self.market,
                    "last": self.last,
                    "candlesize": self.candlesize,
                    "timeframe": self.timeframe,
                    "basesize": self.basesize,
                    "scale": self.scale,
                    "ticks": self.ticks,
                    "eticks": self.eticks,
                    "rticks": self.rticks,
                })


    def buildOutput(self):
        self.apiInfo["help"] = json.dumps({ "message": "no help here buddy" })
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
