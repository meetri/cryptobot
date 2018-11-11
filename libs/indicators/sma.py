import os,sys,talib,numpy,math,logging,time,datetime,numbers
from collections import OrderedDict

from baseindicator import BaseIndicator

class SMA(BaseIndicator):


    def __init__(self,csdata, config = {}):

        config["label"] = config.get("label","sma")
        config["period"] = config.get("period",30)
        config["metric"] = config.get("metric","closed")
        config["label"] = "{}{}".format(config["label"],config["period"])

        BaseIndicator.__init__(self,csdata,config)

        self.data = None
        self.analysis = None
        self.get_analysis()


    def get_settings(self):
        return "{}".format(self.config["period"])


    def details(self, idx ):
        return {
            "name": "sma",
            "period": self.config["period"],
            "metric": self.config["metric"],
            "sma": round(self.data[idx],8),
        }

    def get_charts(self):
        data = []
        for i in range(0,len(self.csdata[ self.config['metric'] ])):
            if isinstance(self.data[i],numbers.Number) and self.data[i] > 0:
                ts = time.mktime(datetime.datetime.strptime(self.csdata["time"][i], "%Y-%m-%dT%H:%M:%SZ").timetuple())
                data.append({
                    "x": ts,
                    "y": self.data[i],
                    })

        return [{
                "key": "{}:{}".format(self.label,self.config["period"]),
                "type": "line",
                "color": "#FFF5EE",
                "yAxis": 1,
                "values": data
                }]


    def get_sma(self):
        if self.csdata is not None:
            try:
                sclosed = self.scaleup( self.csdata[ self.config["metric"] ])
                data = talib.SMA( numpy.array(sclosed), self.config["period"])
                self.data = self.scaledown(data)
                # scaledown
            except Exception as ex:
                self.data = None
                raise ex

        return self.data


    def get_analysis(self ):
        if self.data is None:
            self.get_sma()

        sma = self.data[-1]
        sma1 = self.data[-2]

        slope = None
        candles = 10
        if len(self.data) < candles:
            candles = len(self.data)-1

        for k in range(-1,-1*candles,-1):
            if slope == None and self.data[k] != 0:
                slope = self.data[k-1] / self.data[k]
            elif self.data[k] != 0:
                slope = slope / ( self.data[k-1] / self.data[k] )


        last_price = self.csdata["closed"][-1]
        closing_time = self.csdata["time"][-1]

        action = None

        if sma != None and last_price != None and self.config["metric"] == "closed":
            if last_price < sma:
                action = "oversold"


        res = {
                "weight": 2,
                "time": closing_time,
                "indicator-data": {
                    "sma": sma
                    },
                "analysis": OrderedDict()
                }

        res["analysis"]["name"] = "{}:{}".format(self.get_name(),self.get_settings())
        res["analysis"]["signal"] = action
        res["analysis"]["sma"] = sma
        res["analysis"]["slope"] = slope
        res["analysis"]["order"] = ["sma"]

        self.analysis = res
        return res


    def get_chart_metrics(self,index = 0, scale = 0):
        if scale == 1 and not numpy.isnan(self.data[index]):
            return {
                "sma": self.data[index],
            }

    def format_view(self):
        newres = dict(self.analysis["analysis"])
        newres["slope"] = "{:.4f}".format(newres["slope"])
        newres["sma"] = "{:.8f}".format(newres["sma"])

        return newres



