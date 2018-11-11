import os,sys,logging,time,json,datetime,random,numpy
from trader import Trader
from marketanalyzer import Analyzer
from botdata import BotDataProvider
from tcpsock import TcpSock
from bittrex import Bittrex
from scraper import Scraper
from tradewallet import TradeWallet
from mongowrapper import MongoWrapper
from threading import Thread


class Bot(object):

    def __init__(self, name, config,settings=None):

        self.log = logging.getLogger('crypto')

        self.config = config
        self.name = name
        # self.budget = config.get("budget",0)
        # self.initial_budget = self.budget
        # self.tradelimit = config.get("tradelimit",0)

        self.market  = config.get("market",None)
        self.exchange = config.get("exchange","bittrex")
        self.candlesize = config.get("candlesize","5m")
        self.timeframe  = config.get("timeframe","3d")
        self.basesize  = config.get("basesize","1m")
        self.stopped = False

        if not self.market:
            raise Exception("missing required fields market: {}".format(self.market))

        if "usdt" in self.market.lower():
            self.scale  = config.get("scale",2)
        else:
            self.scale  = config.get("scale",8)


        # sync wallet with database ?
        self.syncWallet = config.get("syncWallet",False)

        #candlestick data
        self.csdata = None
        self.market_summary = None
        self.last = None
        self.scrapeDate = None
        self.startDate = None

        #dataprovider for candlestick data
        self.trader = Trader(market=self.market,exchange=self.exchange)

        #manage indicators
        self.analyzer = None

        #tcp socket
        self.tcpsock = None

        # signal details
        self.history = []

        # bot signals
        self.signals = None

        #cached api results
        self.apiInfo = {}

        #bot settings
        self.defaults = None
        self.setDefaults()
        self.settings = self.updateSettings(settings)

        #threadHandler
        self.thread = None
        self.botSleep = 15
        self.ticks = 0
        self.eticks = 0
        self.rticks = 0
        self.refresh_high = None
        self.refresh_low = None
        self.candle_remaining = None

        wname = "sim:{}:{}".format(self.name,self.market)
        self.simwallet = TradeWallet({'market':self.market,'name':wname,'sync':False,'scale':self.scale})

        wname = "{}:{}".format(self.name,self.market)
        self.wallet = TradeWallet({'market':self.market,'name':wname,'mode':'live','sync':self.syncWallet,'scale':self.scale})

        if self.syncWallet:
            self.wallet.load()
            self.wallet.notify("Traderbot {}: {} started".format(self.name,self.market))

    def configure(self, config ):
        self.config = {
            "market": "",
            "candlesize": "5m",
            "budget": 0.01,
            "maxtrades": 5,
            "target": 0.05,
            "stop": 0.025,
            "notify": ""
            }

        self.config = { **self.config, **config }


    def setDefaults(self):
        self.defaults = {
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

    def updateSettings(self,override = None):
        if override != None:
            self.settings = {**self.defaults,**override}
        else:
            self.settings = self.defaults

        return self.settings


    def score( self, score, csdataIndex, message ):
        self.history.append({
            'candle': self.csdata['time'][csdataIndex],
            "score": score,
            "message": message
            })
        return score


    def getInfo(self, query=None):
        if query in self.apiInfo:
            return self.apiInfo[query]
        elif query == "stop":
            self.stopped = True
            return json.dumps({ "message": "bot stopped" })


    def getSignals(self,idx):
        return { 'signal': None, 'score': 0, 'messages': self.history }


    def buildOutput(self):
        self.apiInfo["help"] = json.dumps({ "message": "no help here buddy" })

    def processRunner(self):
        while not self.stopped:
            try:
                self.process()
                self.ticks += 1
            except Exception as ex:
                print("Error: {}".format(ex))
                self.eticks += 1
                #raise ex

            # print(".",end=" ")
            time.sleep(self.botSleep)


    def start(self):
        self.startDate = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        self.thread = Thread(target=self.processRunner)
        self.thread.start()


    def stop(self):
        self.thread.join()


    def isStopped(self):
        return self.stopped


    def process(self, options = {}):
        return None

    def refresh(self, scrape=False):

        # print("market={},exchange={}".format(self.market, self.exchange))
        scraper = Scraper({'market': self.market, 'exchange': self.exchange})

        self.candle_remaining = self.trader.getCandleRemaining()
        if self.candle_remaining is None:
            csdata = None
            if scrape:
                try:
                    if self.candlesize == "1d" or self.candlesize == "1h":
                        cs = self.candlesize
                    else:
                        cs = "1m"

                    # print('scraping:{}'.format(cs))
                    csdata = scraper.cc_scrapeCandle(cs)
                    self.scrapeDate = datetime.datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
                    self.rticks += 1
                except Exception as ex:
                    print(ex)

                if self.candlesize not in ("1m","1d","1h"):
                    csdata = None

            self.loadCandlesticks(csdata)

        try:
            if self.exchange == "bittrex":
                self.market_summary = Bittrex().public_get_market_summary(self.market).data["result"][0]
            else:
                last = scraper.cc_lastprice()
                self.market_summary = {"Last": last,"Ask":0,"Bid":0}
        except Exception as ex:
            self.market_summary = {"Last": self.csdata["closed"][-1],"Ask":0,"Bid":0}


        self.last = self.market_summary['Last']
        self.csdata['closed'][-1] = self.last

        if self.candle_remaining is not None:
            if self.last > self.refresh_high:
                self.refresh_high == self.last
            if self.last < self.refresh_low:
                self.refresh_low = self.last
        else:
            self.refresh_high = self.csdata["high"][-1]
            self.refresh_low  = self.csdata["low"][-1]

        #self.candle_remaining = self.trader.candle_remaining

        self.csdata["high"][-1] = self.refresh_high
        self.csdata["low"][-1] = self.refresh_low

        self.calculate_ta()


    def lastidx(self):
        return len(self.csdata['closed']) - 1

    def calculate_ta(self):
        self.tadata = {}


    def createSocket( self, ip="127.0.0.1", port=9500 ):
        self.tcpsock = TcpSock(ip,port, self)
        self.tcpsock.start()


    def closeSocket(self):
        self.tcpsock.close()


    def candleColor(self, idx ):
        if self.csdata['closed'][idx] >= self.csdata['open'][idx]:
            return 'green'
        else:
            return 'red'


    def candle(self, idx, ta = None ):
        candle = {
                "date": self.csdata["time"][idx],
                "open": self.csdata["open"][idx],
                "high": self.csdata["high"][idx],
                "low": self.csdata["low"][idx],
                "close": self.csdata["closed"][idx],
                "volume": self.csdata["volume"][idx],
                "basevolume": self.csdata["basevolume"][idx]
                }

        if ta is not None:
            for name in self.tadata:
                if not numpy.isnan(self.tadata[name][idx]):
                    candle.update({name : self.tadata[name][idx]})

        return candle


    def getAnalyzer():
        return self.analyzer


    def getMarket(self):
        return self.market


    def getName(self):
        return self.name


    def getIndicators(self):
        return self.indicators


    def loadCandlesticks(self,csdata=None):
        if csdata == None:
            self.csdata = self.trader.get_candlesticks(self.timeframe,size=self.candlesize,base_size=self.basesize)
        else:
            self.csdata = csdata

        self.analyzer = Analyzer( self.csdata )

