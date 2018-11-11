import os,sys,datetime,numpy,time
#sys.path.append( os.getenv("CRYPTO_LIB","/projects/apps/shared/crypto") )

from bittrex import Bittrex
from cryptocompare import CryptoCompare
from influxdbwrapper import InfluxDbWrapper

class Scraper(object):

    PERIODMAP = {
        "oneMin": "1m",
        "fiveMin": "5m",
        "thirtyMin": "30m",
        "hour": "1h",
        "day": "1d"
        }

    def __init__(self,config = {}):
        self.influxdb_measurement = config.get("influxdb_measurement","market_ohlc")
        self.market = config.get("market","USDT-BTC")
        self.exchange = config.get("exchange","bittrex")
        self.currency = self.market.split("-")[1]

        self.influx = InfluxDbWrapper.getInstance()
        self.bittrex = Bittrex()
        self.cryptocompare = CryptoCompare()

    def cc_lastprice(self):
        resp = self.cryptocompare.lastprice(self.exchange, self.market)
        return resp

    def cc_scrapeCandle(self,period="1m"):
        lasttime = self.getLastCandle(period)
        # print("scraping market: {}, exchange: {}, period {}, last candle: {}".format(self.market,self.exchange,period,lasttime))
        resp = self.cryptocompare.get_candles(self.exchange,self.market,period)
        data = resp.data
        skip = True
        for candle in data["Data"]:
            t = datetime.datetime.utcfromtimestamp(int(candle["time"])).strftime('%Y-%m-%dT%H:%M:%S')
            if lasttime == "" or lasttime == t:
                skip = False

            if lasttime is None:
                skip = False
            else:
                tt = time.mktime(datetime.datetime.strptime(t, "%Y-%m-%dT%H:%M:%S").timetuple())
                lt = time.mktime(datetime.datetime.strptime(lasttime, "%Y-%m-%dT%H:%M:%S").timetuple())
                if lt < tt and skip:
                    # print("missing a lot of data")
                    skip = False

            # print("lasttime = {} , t = {}, skip = {}".format(lasttime,t,skip))
            # if not skip and lasttime != t:
            if not skip:
                item = {
                    "measurement": self.influxdb_measurement,
                    "time": t,
                    "tags": {
                        "currency": self.currency,
                        "period": period,
                        "market": self.market,
                        "exchange": self.exchange,
                        "source": "cryptocompare",
                        },
                    "fields": {
                        "open": float(candle["open"]),
                        "high": float(candle["high"]),
                        "low": float(candle["low"]),
                        "close": float(candle["close"]),
                        "volume": float(candle["volumefrom"]),
                        "base_volume": float(candle["volumeto"])
                        }
                    }
                #print(item)
                self.influx.bulkAdd(item)
                # print("saving exchange: {} market: {} time: {}".format(self.exchange,self.market,t))

        self.influx.bulkSave()
        return self.cc_normalize_candles( data["Data"] )


    def cc_normalize_candles( self, cdata ):
        psize = 0
        cs = { "open": [], "closed": [], "high": [], "low": [], "volume": [], "basevolume": [], "time":[], "opening":[],"closing":[]}
        for point in cdata:
            t = datetime.datetime.utcfromtimestamp(int(point["time"])).strftime('%Y-%m-%dT%H:%M:%S')
            psize += 1
            cs["low"].extend([point["low"]])
            cs["high"].extend([point["high"]])
            cs["closed"].extend([point["close"]])
            cs["open"].extend([point["open"]])
            cs["volume"].extend([float(point["volumefrom"])])
            cs["basevolume"].extend([float(point["volumeto"])])
            cs["time"].extend([t])


        return {
                "low": numpy.array(cs["low"]),
                "high": numpy.array(cs["high"]),
                "closed": numpy.array(cs["closed"]),
                "volume": numpy.array(cs["volume"]),
                "basevolume": numpy.array(cs["basevolume"]),
                "open": numpy.array(cs["open"]),
                "time": cs["time"],
                }

    def scrapeCandle(self,period):
        lasttime = self.getLastCandle(Scraper.PERIODMAP[period])
        # print("scraping market: {}, period {}, last candle: {}".format(self.market,period,lasttime))
        resp = self.bittrex.public_get_candles(market=self.market,tickInterval=period)
        data = resp.data
        skip = True
        for candle in data["result"]:
            if lasttime == "" or lasttime == candle["T"]:
                skip = False

            if not skip and lasttime != candle["T"]:
                item = {
                    "measurement": self.influxdb_measurement,
                    "time": candle["T"],
                    "tags": {
                        "currency": self.currency,
                        "period": Scraper.PERIODMAP[period],
                        "market": self.market,
                        "exchange": self.exchange,
                        },
                    "fields": {
                        "open": float(candle["O"]),
                        "high": float(candle["H"]),
                        "low": float(candle["L"]),
                        "close": float(candle["C"]),
                        "volume": float(candle["V"]),
                        "base_volume": float(candle["BV"])
                        }
                    }
                self.influx.bulkAdd(item)
                # print("saving exchange: {} market: {} time: {}".format(self.exchange,self.market,candle["T"]))

        self.influx.bulkSave()


    def getLastCandle(self,period):
        query = """SELECT base_volume FROM "{}" WHERE market='{}' AND period='{}' AND exchange='{}' ORDER BY time DESC LIMIT 2 """.format(self.influxdb_measurement,self.market,period, self.exchange )

        res = list(self.influx.raw_query(query).get_points())

        if len(res) > 1:
            return res[1]["time"][:-1]



