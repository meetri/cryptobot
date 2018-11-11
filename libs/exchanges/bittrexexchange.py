from bittrex import Bittrex

class BittrexExchange(object):

    def __init__(self, config = {} ):
        self.api = Bittrex()
        self.balance = None


    def buy(self, buyOrder ):
        r = self.api.market_buylimit( buyOrder["market"], buyOrder["qty"], buyOrder["price"] ).getData()
        if r["success"]:
            buyOrder["id"] = r["result"]["uuid"]
        else:
            buyOrder["status"] = "error"

        return buyOrder


    def sell(self, sellOrder):
        r = self.api.market_selllimit( sellOrder["market"], sellOrder["qty"], sellOrder["price"] ).getData()
        if r["success"]:
            sellOrder["id"] = r["result"]["uuid"]
        else:
            sellOrder["status"] = "error"
            print(r)
        return sellOrder


    def cancel(self, orderId):
        r = self.api.market_cancel( orderId ).getData()
        return r


    def getOrderStatusDirect(self,orderId):
        r = self.api.account_get_order( orderId ).getData()
        return r


    def getOrderStatus(self, orderId):
        resp = self.getOrderStatusDirect(orderId)
        # print(resp)

        status = "pending"

        if resp["result"]["Quantity"] != resp["result"]["QuantityRemaining"]:
            status = "partial"

        if not resp["result"]["IsOpen"]:
            status = "completed"

        if resp["result"]["CancelInitiated"]:
            status = "cancelled"

        return {
                "status": status,
                "remaining": resp["result"]["QuantityRemaining"],
                "commissionPaid": resp["result"]["CommissionPaid"],
                "opened": resp["result"]["Opened"],
                "closed": resp["result"]["Closed"]
                }




    def processOrder(self, order ):
        order.setExchange( self.getName() )
        self.log.info("bittrex exchange processing order")
        if order.rate != order.MARKET:
            if order.order_type == order.SELL:
                r = self.api.market_selllimit( order.market, order.qty, order.rate ).getData()
            elif order.order_type == order.BUY:
                r = self.api.market_buylimit( order.market, order.qty, order.rate ).getData()

            if r["success"]:
                order.ref_id = r["result"]["uuid"]
                order.status = order.OPEN
            else:
                order.status = order.ERROR

            order.meta["api"] = {
                    "create": r
                    }
            res = order.save()
            self.log.info("save results {}".format(res))
            return Result(r["success"],r["message"],r["result"])
        else:
            return Result.fail("Market orders not allowed on bittrex")


    def syncOrder(self,order):
        if order.status < order.TERMINATED_STATE:
            status = order.status
            results = self.api.account_get_order( order.ref_id )
            data = results.getData()
            if data["success"]:
                res = data["result"]
                if res["CancelInitiated"]:
                    order.status = order.CANCELLED
                elif not res["IsOpen"] and res["Type"] == "LIMIT_SELL":
                    order.status = order.COMPLETED
                elif not res["IsOpen"] and res["Type"] == "LIMIT_BUY":
                    order.status = order.FILLED
                elif res["IsOpen"] and not res["Quantity"] > res["QuantityRemaining"] and order.status != order.PARTIAL_FILL:
                    order.status = order.PARTIAL_FILL

                if status != order.status or "state" not in order.meta["api"]:
                    self.log.info("found updates to order {}".format(order.ref_id))
                    order.meta["api"]["state"] = data
                    order.save()
                    if order.status == order.COMPLETED: # and order.order_type == Order.SELL:
                        self.log.info("looking for associated order: {}".format(order.assoc_id))
                        assocorder = Order.findById(order.assoc_id)
                        if assocorder.isOk():
                            aorder = assocorder.data["results"][0]
                            aorder.status = Order.COMPLETED
                            self.log.info("found associated order {}".format(aorder.ref_id))
                            #instead get this rate from the api results...
                            aorder.meta["sold_at"] = data["result"]['PricePerUnit']
                            aorder.assoc_id = order.pkey #data["result"]['PricePerUnit']
                            res = aorder.save()
                            self.log.info("saved associated order {}".format(res))

                    return True


    def getBalance(self,currency):
        if self.balance is None:
            self.getBalances()

        currency = currency.upper()
        if currency in self.balance:
            return self.balance[currency]["Available"]


    def getBalances(self):
        results = self.api.account_get_balances().getData()
        if results["success"]:
            self.balance = {}
            for c in results["result"]:
                self.balance[c["Currency"]] = c

        return self.balance


