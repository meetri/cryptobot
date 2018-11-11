import random,uuid,os
from datetime import datetime
from mongowrapper import MongoWrapper
from twiliosms import TwilioSms


class TradeWallet(object):

    def __init__( self, config = {}):

        self.buys = []
        self.rejected = []
        self.sells = []
        self.reports = []

        self.name = config.get("name","sim1")
        self.market = config.get("market","")
        self.sync = config.get("sync",True)
        self.scale = config.get("scale",8)
        self.maxtrades = config.get("trades",5)


        if self.scale == 2:
            self.budget = config.get("budget",100)
        else:
            self.budget = config.get("budget",0.1)

        self.qtyVal = self.budget / self.maxtrades

        self.sellGoalPercent = config.get("sellGoalPercent",0.05)
        self.stopLossPercent = config.get("sellGoalPercent",-0.025)

        self.sms = TwilioSms.getInstance()
        self.notifyList = os.getenv("TRADEBOT_NOTIFY","")

        #mongodb
        self.mongo = MongoWrapper.getInstance().getClient()
        self.exchange = None


    def reset(self):
        self.buys = []
        self.rejected = []
        self.sells = []
        self.reports = []


    def notify(self,msg):
        if self.sync:
            if len(msg) > 0:
                nl = self.notifyList.split(",")
                for number in nl:
                    self.sms.send(msg,number)


    def getResults(self, lastprice = None ):

        totalShorts = 0
        for trade in self.sells:
            if trade["type"] in ["short"]:
                totalShorts+=1

        openTrades = 0
        totalprofit = 0
        for trade in self.buys:
            # if trade["status"] not in ["completed","sold","forsale"]:
            if trade["sell_id"] is None and trade["status"] not in ["cancelled"]:
                openTrades+=1
                if lastprice is not None:
                    totalprofit += (lastprice - trade["price"])*trade["qty"]

        total = 0
        totalSells = 0
        for trade in self.sells:
            if trade["type"] == "sell":
                totalSells += 1
                profit = (trade["price"] - trade["buy_price"]) * trade["qty"]
                # print("{:.8f}-{:.8f}={:.8f}".format(trade['price'],trade['buy_price'],profit))
                total += profit

        totalTrades = totalSells  + len(self.buys)

        return {
                "last": lastprice,
                "totalTrades": totalTrades,
                "totalBuys": len(self.buys),
                "totalSells": totalSells,
                "totalShorts": totalShorts,
                "openTrades": openTrades,
                "sellprofit": "{:.8f}".format(total),
                "openprofit": "{:.8f}".format(totalprofit),
                "totalprofit": "{:.8f}".format(totalprofit+total)
                }


    def exchangeSync(self):
        if self.exchange is None:
            return

        for buy in self.buys:
            if buy["status"] in ["pending","partial"]:
                buy.update(self.exchange.getOrderStatus(buy['id']))
                if buy["status"] in ["completed","cancelled"]:
                    self.notify("Market {} {} buy of {} units @ {:.8f}".format(self.market,buy["status"],buy["qty"],buy["price"]))

        for sell in self.sells:
            if sell["status"] in ["pending","partial"]:
                sell.update(self.exchange.getOrderStatus(sell['id']))
                if sell["status"] in ["completed","cancelled"]:
                    self.notify("Market {} {} sell of {} units @ {:.8f}".format(self.market,sell['status'],sell["qty"],sell["price"]))

        self.update()



    def setup(self):
        res = self.mongo.crypto.drop_collection("wallet")
        res = self.mongo.crypto.wallet.create_index([("name",pymongo.ASCENDING)],unique=True)


    def update(self):
        if self.sync:
            doc = { 'name': self.name, 'buys': self.buys, 'sells': self.sells, 'rejected': self.rejected }
            return self.mongo.crypto.wallet.replace_one({'name':self.name},doc,upsert=True)


    def load(self):
        if self.sync:
            res = self.mongo.crypto.wallet.find_one({'name':self.name})
            if res is not None and 'name' in res:
                self.buys = res['buys']
                self.sells = res['sells']
                if "rejected" in res:
                    self.rejected = res['rejected']
            return res


    def report(self, candle, signals = None, timeIndex = None ):
        if self.exchange is None:
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        self.reports.append( {
            'type': 'report',
            'date': utcnow,
            'index': timeIndex,
            'candle': candle['date'],
            'price': candle['close'],
            'signals': signals
            })


    def short(self, candle, price = None, signals = None, timeIndex = None):
        '''used as an indicator predicting the market will be taking a down turn'''

        self.checkSales(short=True,candle=candle,price=price,timeIndex=timeIndex,signals=signals)


    def getSignals(self):
        sigevent = []
        sigevent.extend(self.buys)
        sigevent.extend(self.sells)
        #sigevent.extend(self.reports)
        return sigevent


    def buyCheck(self, buyobj ):

        reject = False

        rejCount = 2
        for buy in self.buys:
            if buy['sell_id'] is None and buy['status'] not in ['cancelled']:
                if buy['candle'] == buyobj['candle']:
                    reject = True

                if buy['price'] <= buyobj['price']:
                    rejCount -= 1
                #TODO: Add time restraints...
                #if buyobj['price'] > buy['price'] - (buy['price'] * 0.03):
                #    reject = True


        if rejCount <= 0:
            reject = True

        res = self.getResults()
        price = buyobj["price"]
        if res['openTrades'] >= self.maxtrades:
            reject = True

        return not reject

    def createBuy(self,market,price,qty,buydate=None,goalPercent=0.05,stopLossPercent=None):
        """create buy order"""

        utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
        if buydate is None:
            buydate = utcnow

        buyid = "watch-{}".format(str(uuid.uuid4()))

        if goalPercent is None:
            goalPercent = self.sellGoalPercent

        stopLossPrice = None
        if stopLossPercent is not None:
            stopLossPrice = self.getPriceFromPercent(price,stopLossPercent)

        goalPrice = self.getPriceFromPercent(price,goalPercent)

        buyObj = {
            'id': buyid,
            'sell_id': None,
            'status': 'completed',
            'type': 'buy',
            'date': utcnow,
            'market': market,
            'candle': buydate,
            'index': 0,
            'price': price,
            'qty': qty,
            'goalPercent': goalPercent,
            'goalPrice': goalPrice,
            'stopLossPrice': stopLossPrice
            }
        self.buys.append(buyObj)
        self.update()


    def buy(self, goalPercent=None, goalPrice=None, price= None, signals = None, timeIndex = None, candle=None, qty = None):
        '''create new buy order'''

        if candle is None:
            candle = { "date":datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S') }

        if self.exchange is None:
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if goalPrice is None:
            if goalPercent is None:
                goalPercent = self.sellGoalPercent
            goalPrice = self.getPriceFromPercent(price,goalPercent)

        stopLossPrice = None
        if self.stopLossPercent is not None:
            stopLossPrice = self.getPriceFromPercent(price,self.stopLossPercent)

        if qty is None:
            qty = self.qtyVal / price

        buyid = "sim-{}".format(str(uuid.uuid4()))
        buyObj = {
            'id': buyid,
            'sell_id': None,
            'status': 'pending',
            'type': 'buy',
            'date': utcnow,
            'market': self.market,
            'candle': candle['date'],
            'index': timeIndex,
            'price': price,
            'qty': qty,
            'goalPercent': goalPercent,
            'goalPrice': goalPrice,
            'stopLossPrice': stopLossPrice,
            'signals': signals
            }

        if self.buyCheck(buyObj):
            if self.exchange is not None:
                buyObj = self.exchange.buy( buyObj )
            else:
                buyObj["status"] = "completed"

            self.buys.append( buyObj )
            self.update()
            self.notify("Market {} bid {} units  @ {:.8f} btc".format(self.market,buyObj["qty"],buyObj["price"]))
        else:
            buyObj["status"] = "rejected"
            self.rejected.append ( buyObj )
            #self.update()

        return buyObj


    def sell(self, buydata, saledata = None, price=None, signals = None, timeIndex = None):
        '''place buy order in sell queue'''

        if saledata is None:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')
            if price is not None:
                saleprice = price
            else:
                saleprice = buydata["goalPrice"]
        else:
            saleprice = saledata['price']
            utcnow = saledata['date']

        sellid = "sim-{}".format(str(uuid.uuid4()))
        sellObj = {
                'id': sellid,
                'market': buydata['market'],
                'status': 'pending',
                'type': 'sell',
                'date': utcnow,
                'index': timeIndex,
                'price': saleprice,
                'qty': buydata['qty'],
                'buy_price': buydata['price'],
                'buy_id': buydata['id'],
                'signals': signals
                }

        buydata['sell_id'] = sellObj["id"]
        if self.exchange is not None:
            sellObj = self.exchange.sell(sellObj)
        else:
            sellObj["status"] = "completed"


        self.sells.append(sellObj)
        self.update()

        self.notify("Market {} ask {} units  @ {:.8f} btc ".format(self.market,sellObj["qty"],sellObj["price"]))
        return sellObj



    # TODO:
    def getPriceFromPercent(self, price, percent ):
        print(price)
        print(percent)
        return (price * percent) + price


    def isForSale(self, candle, price, buydata,short=False,checkStops = False):

        if buydata["status"] not in ["completed"] or buydata["sell_id"] is not None:
            return { "status": False }

        goalPrice = buydata['goalPrice']
        if goalPrice is None:
            goalPrice = self.getPriceFromPercent(buydata['price'],buydata['goalPercent'])

        if self.exchange is None:
            utcnow = candle['date']
        else:
            utcnow = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        if checkStops:
            forsale = buydata["stopLossPrice"] is not None and price <= buydata["stopLossPrice"]
        else:
            forsale = short or price >= goalPrice

        return {
                "status": forsale,
                "price":price,
                "date": utcnow,
                "buy":buydata['price'],
                "goal":goalPrice,
                "goalPercent": buydata['goalPercent']
                }


    def checkSales(self,candle, price, timeIndex = None, shortScore = 0, short = False, signals = None):
        sold = False
        for buydata in self.buys:
            sale = self.isForSale(candle,price,buydata,short=short)
            if sale['status']:
                self.sell( buydata, saledata=sale, timeIndex=timeIndex, signals=signals )
                sold = True
        return sold


    def checkStops(self,candle, price, timeIndex = None, shortScore = 0, short = False, signals = None):
        sold = False
        for buydata in self.buys:
            sale = self.isForSale(candle,price,buydata,short=short,checkStops=True)
            if sale['status']:
                self.sell( buydata, saledata=sale, timeIndex=timeIndex, signals=signals )
                sold = True
        return sold
