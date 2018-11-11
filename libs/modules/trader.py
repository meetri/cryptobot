import os,sys,talib,numpy,math,time,datetime
from influxdbwrapper import InfluxDbWrapper
from coincalc import CoinCalc
from exchange import Exchange

class Trader(object):

    def __init__(self, market = None, exchange=None, currency=None):
        self.influxdb = InfluxDbWrapper.getInstance()
        self.market = market
        if exchange is None:
            exchange = "bittrex"
        self.exchange = exchange
        self.cs = None
        self.indicators = None
        self.timeframe = None
        self.cssize = None
        self.candle_seconds = 0
        self.candle_remaining = 0
        self.candle_last_time = None
        if currency is not None:
            self.market = CoinCalc.getInstance().get_market(currency)


    def set_currency(self,currency):
        self.market = CoinCalc.getInstance().get_market(currency)
        return self

    def project_volume( volkey = "basevolume" ):
        size = self.cssize

        m = 1
        if size[-1] == "m":
            m = 60
        elif size[-1] == "h":
            m = 3600
        elif size[-1] == "d":
            m = 86400

        sec_ofs = float(size[0:-1]) * m
        ts = time.time() % sec_ofs

        remaining = sec_ofs - ts
        rem = sec_ofs / ( sec_ofs - remaining)
        return cs[volkey][-1] * rem

    def getCandleRemaining(self):
        rem = None
        if self.candle_last_time is not None:
            ts = time.time() - self.candle_last_time
            if ts < self.candle_remaining:
                return self.candle_remaining - ts
        return rem

    def get_candlesticks(self, timeframe = "1h", size = "1m", dateOffset = "now()" , base_size="1m"):
        self.timeframe = timeframe
        self.cssize = size

        m = 1
        if size[-1] == "m":
            m = 60
        elif size[-1] == "h":
            m = 3600
        elif size[-1] == "d":
            m = 86400

        sec_ofs = float(size[0:-1]) * m
        ts = time.time() % sec_ofs

        if len(base_size) > 0:
            dateOffset = (datetime.datetime.utcnow() - datetime.timedelta(seconds=ts) + datetime.timedelta(seconds=sec_ofs)).strftime('%Y-%m-%dT%H:%M:%SZ')

            pres = self.influxdb.raw_query("""SELECT SUM(base_volume) AS base_volume, SUM(volume) AS volume, MAX(high) as high, MIN(low) as low, FIRST(open) as open, LAST(close) AS close FROM "market_ohlc" WHERE market='{0}' AND exchange='{5}' AND time < '{1}' AND time > '{1}' - {2} AND period='{4}' GROUP BY time({3})""".format(self.market,dateOffset,timeframe,size,base_size,self.exchange))
            points = pres.get_points()

        else:
            points = self.influxdb.raw_query("""select base_volume, volume, open, high, low, close FROM "market_ohlc" WHERE market='{0}' AND exchange='{4}' AND time < {1} AND time > {1} - {2} AND period='{3}'""".format(self.market,dateOffset,timeframe,size,self.exchange)).get_points()


        cs = self.clear_candlesticks()

        psize = 0
        for point in points:
            if point["volume"] == None:
                continue
                #point["volume"] = 0

            #if point["base_volume"] == None:
            #    point["base_volume"] = 0

            psize += 1
            cs["low"].extend([point["low"]])
            cs["high"].extend([point["high"]])
            cs["closed"].extend([point["close"]])
            cs["open"].extend([point["open"]])
            cs["volume"].extend([float(point["volume"])])
            cs["basevolume"].extend([float(point["base_volume"])])
            cs["time"].extend([point["time"]])

        self.candle_remaining = sec_ofs - ts
        self.candle_seconds = sec_ofs
        self.candle_last_time = time.time()




        if psize == 0:
            raise Exception("no market data for {} at {}".format(self.market,dateOffset))

        self.cs = {
                "low": numpy.array(cs["low"]),
                "high": numpy.array(cs["high"]),
                "closed": numpy.array(cs["closed"]),
                "volume": numpy.array(cs["volume"]),
                "basevolume": numpy.array(cs["basevolume"]),
                "open": numpy.array(cs["open"]),
                "time": cs["time"],
                "remaining": numpy.array(cs["remaining"]),
                "projected_volume": numpy.array(cs["projected_volume"]),
                "projected_basevolume": numpy.array(cs["projected_basevolume"]),
                }

        Exchange.getInstance().set_market_value(self.market, self.cs["closed"][-1] )
        return self.cs


    def x_get_candlesticks(self, timeframe = "1h", size = "5m", dateOffset = "now()" ):
        self.timeframe = timeframe
        self.cssize = size
        points = self.influxdb.raw_query("""select LAST(basevolume) as basevolume, LAST(volume) as volume, FIRST(last) as open, LAST(last) as closed, MAX(last) as high, MIN(last) as low FROM "market_summary" WHERE marketname='{0}' and time < {1} and time > {1} - {2}  group by time({3})""".format(self.market,dateOffset,timeframe,size)).get_points()

        cs = self.clear_candlesticks()

        psize = 0
        for point in points:
            psize += 1
            cs["low"].extend([point["low"]])
            cs["high"].extend([point["high"]])
            cs["closed"].extend([point["closed"]])
            cs["open"].extend([point["open"]])
            cs["volume"].extend([point["volume"]])
            cs["basevolume"].extend([point["basevolume"]])
            cs["time"].extend([point["time"]])

        if psize == 0:
            raise Exception("no market data for {} at {}".format(self.market,dateOffset))

        def fix_gaps(lst):
            for idx,val in enumerate(lst):
                if val == None:
                    if idx > 0:
                        lst[idx] = lst[idx-1]
                    if idx == 0:
                        lst[idx] = 0

        fix_gaps(cs["low"])
        fix_gaps(cs["high"])
        fix_gaps(cs["closed"])
        fix_gaps(cs["open"])
        fix_gaps(cs["volume"])
        fix_gaps(cs["basevolume"])
        fix_gaps(cs["time"])


        self.cs = {
                "low": numpy.array(cs["low"]),
                "high": numpy.array(cs["high"]),
                "closed": numpy.array(cs["closed"]),
                "volume": numpy.array(cs["volume"]),
                "basevolume": numpy.array(cs["basevolume"]),
                "open": numpy.array(cs["open"]),
                "time": cs["time"]
                }

        Exchange.getInstance().set_market_value(self.market, self.cs["closed"][-1] )
        return self.cs

    def xget_candlesticks(self, timeframe = "1h", size = "5m" ):
        self.timeframe = timeframe
        self.cssize = size
        points = self.influxdb.raw_query("""select FIRST(last) as open, LAST(last) as closed, MAX(last) as high, MIN(last) as low, (LAST(basevolume)+LAST(volume)) as volume FROM "market_summary" WHERE marketname='{}' and time > now() - {} group by time({})""".format(self.market,timeframe,size)).get_points()

        cs = self.clear_candlesticks()

        for point in points:
            cs["low"].extend([point["low"]])
            cs["high"].extend([point["high"]])
            cs["closed"].extend([point["closed"]])
            cs["open"].extend([point["open"]])
            cs["volume"].extend([point["volume"]])
            cs["basevolume"].extend([point["basevolume"]])
            cs["time"].extend([point["time"]])

        def fix_gaps(lst):
            for idx,val in enumerate(lst):
                if val == None:
                    if idx > 0:
                        lst[idx] = lst[idx-1]
                    if idx == 0:
                        lst[idx] = 0

        fix_gaps(cs["low"])
        fix_gaps(cs["high"])
        fix_gaps(cs["closed"])
        fix_gaps(cs["open"])
        fix_gaps(cs["volume"])
        fix_gaps(cs["basevolume"])
        fix_gaps(cs["time"])


        self.cs = {
                "low": numpy.array(cs["low"]),
                "high": numpy.array(cs["high"]),
                "closed": numpy.array(cs["closed"]),
                "volume": numpy.array(cs["volume"]),
                "basevolume": numpy.array(cs["basevolume"]),
                "open": numpy.array(cs["open"]),
                "time": cs["time"]
                }

        Exchange.getInstance().set_market_value(self.market, self.cs["closed"][-1] )
        return self.cs


    def clear_candlesticks(self):
        return { "open": [], "closed": [], "high": [], "low": [], "volume": [], "basevolume": [], "time":[], "opening":[],"closing":[],"remaining":[],"projected_volume":[],"projected_basevolume":[] }


