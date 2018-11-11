"""
Coinmarketcap pro api
"""

import os
from genericapi import GenericApi


class CoinMarketCap(GenericApi):

    def __init__(self):

        config = {
                "apiroot": "https://pro-api.coinmarketcap.com/v1/"
                # "apiroot": "https://sandbox-api.coinmarketcap.com/v1/"
            }
        GenericApi.__init__(self, config)

        self.headers["X-CMC_PRO_API_KEY"] = os.getenv("CMC_KEY", "")

    def topList(self):
        pl = {
                "start": 1,
                "limit": 5000,
                "convert": "USD"
                }
        ret = self.process("cryptocurrency/listings/latest", payload=pl, method="get" )
        return ret.data


