#!/usr/bin/env python3 -u
import os,sys,json,time,cherrypy,cherrypy_cors
curdir = os.path.dirname(os.path.realpath(__file__))
sys.path.append( os.getenv("CRYPTO_LIB","/projects/apps/shared/crypto") )

import cryptolib
from basesbot import BasesBot

MARKET_SEL = os.getenv("MARKET","USDT-BTC")
BOT_PORT = int(os.getenv("BOT_PORT","9500"))
BOT_NAME = os.getenv("BOT_NAME","SimBot3")
TIMEFRAME = os.getenv("TIMEFRAME","72h")

SETTINGS = os.getenv("SETTINGS")
#SETTINGS = os.getenv("SETTINGS",'{"rsi.buy":39,"rsi.sell":63}')
#SETTINGS = os.getenv("SETTINGS",'{"rsi.buy":39,"rsi.sell":50}')

class DoSomething(object):

    def __init__(self, bot):
        self.bot = bot

    @cherrypy.expose
    def index(self,cmd="help"):
        return self.bot.getInfo(cmd)


if __name__ == "__main__":
    cherrypy_cors.install()
    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': BOT_PORT})

    if SETTINGS is not None and len(SETTINGS) > 0:
        settings = json.loads(SETTINGS)
        print("SETTINGS:")
        print(settings)
    else:
        settings = None

    bot = BasesBot(config={"market":MARKET_SEL,"timeframe":TIMEFRAME},name=BOT_NAME,settings=settings)
    bot.run_simulation()
    bot.start()

    config = {'/':{'cors.expose.on': True}}
    try:
        cherrypy.quickstart ( DoSomething(bot), config=config )
    except (KeyboardInterrupt,SystemExit):
        print("exiting...")
        bot.stop();

