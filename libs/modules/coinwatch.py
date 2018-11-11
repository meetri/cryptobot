from bittrex import Bittrex
from mongowrapper import MongoWrapper
from bson.objectid import ObjectId

class CoinWatch(object):

    def __init__(self, config={}):
        self.bittrex = Bittrex()
        self.mongo = MongoWrapper.getInstance().getClient()
        self.history = None
        self.pendingorders = None
        self.bal = None

    def setupWatch(self):
        res = self.mongo.crypto.drop_collection("watch")
        #res = self.mongo.crypto.create_collection("watch")
        #res = self.mongo.crypto.watch.create_index([("name",pymongo.ASCENDING)],unique=True)


    def updateWatch(self, watch ):
        if "_id" in watch:
            searchDoc = {"_id": ObjectId(watch["_id"])}
            del watch["_id"]
        else:
            searchDoc = {"name": watch.get("name"), "exchange": watch.get("exchange")}
        return self.mongo.crypto.watchlist.replace_one(searchDoc, watch , upsert=True)


    def update(self, watch):
        if "name" in watch:
            return self.mongo.crypto.watchlist.replace_one({'name':watch['name']},watch,upsert=True)

    def removeWatch(self, market,exchange):
        if market is not None:
            return self.mongo.crypto.watchlist.delete_one({'name':market, 'exchange': exchange})


    def loadWatchList(self,search = {}):
        res = self.mongo.crypto.watchlist.find(search)
        allrows = list(res)
        watchlist = []
        headers = []
        for row in allrows:
            for key in row:
                if key not in headers:
                    headers.append(key)

        for row in allrows:
            r = {}
            for head in headers:
                if head in row:
                    r[head] = row[head]
                else:
                    r[head] = None
            watchlist.append(r)

        return watchlist

    def refresh(self):
        self.history  = self.bittrex.account_get_orderhistory().data["result"]
        self.bal = self.bittrex.account_get_balances().data["result"]
        self.pendingorders = self.bittrex.market_get_open_orders().data["result"]

    def tableize(self, rows, headers = None, margin = 2):

        if len(rows) == 0:
            return

        headers = []
        mincol = {}
        for row in rows:
            for c in row:
                col = str(c)
                if col not in headers:
                    headers.append(col)
                    mincol[col] = len(col)

        for row in rows:
            for head in headers:
                if head in row:
                    hl = len(str(row[head]))
                    if hl > mincol[head]:
                        mincol[head] = hl

        for head in headers:
            print("{}".format(head.ljust(mincol[head]+margin)), end="")
        print("")

        for row in rows:
            for head in headers:
                if head in row and row[head] is not None:
                    col = str(row[head])
                else:
                    col = ""

                print("{}".format(col.ljust(mincol[head]+margin)), end="")
            print("")

    def xtableize(self, rows):

        hid = 0
        hl = 0
        for idx, row in enumerate(rows):
            if len(row) > hl:
                hl = len(row)
                hid = idx

        mincol = []
        if len(rows) == 0:
            return

        for head in rows[hid]:
            mincol.append(len(head))

        for row in rows:
            for idx,head in enumerate(row):
                col = str(row[head])
                l = mincol[idx]
                mincol[idx] = max(len(col),l)

        for idx,head in enumerate(rows[hid]):
            print("{}".format(head.ljust(mincol[idx]+2)),end="")
        print("")

        for row in rows:
            for idx,head in enumerate(row):
                col = str(row[head])
                print("{}".format(col.ljust(mincol[idx]+2)),end="")
            print("")

    def getPricePercentDif(self, price1, price2):
        price1 = float(price1)
        price2 = float(price2)
        return ((price1 - price2) * 100) / price1

    def getPriceFromPercent(self, price, percent ):
        return (price * percent) + price

    def order_summary(self, currency, details=False):
        orders = []
        for idx, order in enumerate(reversed(self.history)):
            if order["Exchange"].endswith("-{}".format(currency)):
                if "OrderUuid" in order:
                    del order['OrderUuid']
                if "ConditionTarget" in order:
                    del order['ConditionTarget']
                if "Commission" in order:
                    del order['Commission']
                if "IsConditional" in order:
                    del order['IsConditional']
                if "TimeStamp" in order:
                    del order['TimeStamp']
                if "ImmediateOrCancel" in order:
                    del order['ImmediateOrCancel']
                if "Condition" in order:
                    del order['Condition']
                orders.append(order)

        if details:
            return orders

        qty = 0
        olist = []
        for order in orders:
            q = order["Quantity"] - order["QuantityRemaining"]
            if order["OrderType"] == "LIMIT_BUY":
                olist.append({'market': order["Exchange"], 'qty': q, "price": order["PricePerUnit"]})
                qty += q
            elif order["OrderType"] == "LIMIT_SELL":
                qty -= q
                for buy in olist:
                    if buy['qty'] > q:
                        buy['qty'] -= q
                        q = 0
                    else:
                        q = q - buy['qty']
                        buy['qty'] = 0


        markets = {}

        for order in olist:
            if order['qty'] > 0:
                market = order["market"]
                if market not in markets:
                    markets[market] = self.buildWatcher(order={
                        "market": market,
                        "price": order["price"],
                        "total": order["price"] * order["qty"],
                        "qty": order["qty"],
                        "orders": 1
                        })
                else:
                    markets[market]["price"] += order["price"]
                    markets[market]["total"] += order["price"] * order["qty"]
                    markets[market]["qty"] += order["qty"]
                    markets[market]["orders"] += 1

        for market in markets:
            tick = self.bittrex.public_get_ticker(market).data["result"]
            avgPrice = markets[market]["total"] / markets[market]["qty"]
            markets[market]['price'] = avgPrice
            # markets[market]['price'] /= markets[market]['orders']
            markets[market]['last'] = "{:.08f}".format(tick['Last'])
            markets[market]['bid'] = "{:.08f}".format(tick['Bid'])
            markets[market]['ask'] = "{:.08f}".format(tick['Ask'])
            avgPrice = markets[market]["total"] / markets[market]["qty"]
            # markets[market]['avg'] = avgPrice
            markets[market]['dif'] = "{:.02f}".format(self.getPricePercentDif( tick["Last"], avgPrice))
            markets[market]['total'] = markets[market]['qty'] * tick["Last"]
            markets[market]['exchange'] = "bittrex"

        return markets

    def buildWatcher(self, order):
        obj = {
            "market": "",
            "price": 0,
            "qty": 0,
            "orders": 0,
            "last": 0,
            "bid": 0,
            "ask": 0,
            "dif": 0,
            "total": 0,
        }
        obj.update(order)
        return obj

    def cancelOrder(self,orderId):
        mc = self.bittrex.market_cancel(orderId)
        return mc.data["success"]

    def parsePending(self):
        if self.pendingorders is None:
            self.refresh()

        out = []
        for order in self.pendingorders:
            out.append({
               "oid": order["OrderUuid"],
               "exchange": order["Exchange"],
               "type": order["OrderType"],
               "qty": order["Quantity"],
               "remaining": order["QuantityRemaining"],
               "Limit": "{:.08f}".format(order["Limit"]),
               "Openend": order["Opened"],
               "Closed": order["Closed"],
               #"Cancelled": order["ImmediateOrCancelled"]
               })

        return out

    def parse(self, market=None):
        if self.bal is None:
            self.refresh()

        acc = []
        rows = []
        for account in self.bal:
            if account['Balance'] > 0:
                if account["Currency"] not in ["USDT", "BTC"] and \
                   (market is None or market in account["Currency"].lower()):
                    summary = self.order_summary(account["Currency"],
                                                 market is not None)
                    rows.append(summary)
                    acc.append(account)

        if market is not None:
            return rows[0]

        out = []
        for row in rows:
            for market in row:
                m = row[market]
                out.append(m)

        return out
