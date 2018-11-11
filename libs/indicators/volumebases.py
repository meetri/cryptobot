import os,sys,talib,numpy,math,logging,time,datetime,numbers
from collections import OrderedDict

from baseindicator import BaseIndicator

class VolumeBases(BaseIndicator):

    def __init__(self,csdata, vsma, config = {}):
        BaseIndicator.__init__(self,csdata,config)

        self.vmx = config.get("vmx",10)
        self.md = config.get("md",0.004)
        self.vsma = vsma
        self.data = []

        self.getBases()

    def getBases(self,simIdx = None):

        bases = []
        for idx,t in enumerate( self.csdata["time"]):
            if simIdx is None or simIdx <= idx:
                try:
                    if not numpy.isnan(self.csdata["volume"][idx]) and not numpy.isnan(self.vsma[idx]) and self.vsma[idx] != 0:
                        mx = self.csdata["volume"][idx] / self.vsma[idx]
                        if mx > self.vmx:
                            self.addBase(bases,idx,"low")
                            self.addBase(bases,idx,"high")
                except Exception as ex:
                    print("Error: vol:{}, vsma:{}\nError: {}".format(self.csdata["volume"][idx],self.vsma[idx],ex))

        def sortbase(e):
            return e["price"]

        self.data = sorted(bases,key=sortbase,reverse=True)
        return self


    def addBase(self, bases, idx, item ):
        price = self.csdata[item][idx]
        found = False
        for base in bases:
            df = max(price,base['price']) / min(price,base['price'])
            df -= 1
            if df <= self.md:
                found = True

        if not found:
            bases.append({
                "price": price,
                "item": item,
                "candle": self.csdata["time"][idx]
            })

