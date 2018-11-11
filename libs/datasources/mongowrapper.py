import os
import pymongo
import urllib.parse

class MongoWrapper(object):

    _instance = None

    def __init__(self,host="localhost",port="27017",username="crypto",password="helloworld",dbname="crypto"):
        username = urllib.parse.quote_plus(os.getenv("MONGO_USER",username))
        password = urllib.parse.quote_plus(os.getenv("MONGO_PASS",password))
        host = os.getenv("MONGO_HOST",host)
        port = int(os.getenv("MONGO_PORT",port))
        dbname = os.getenv("MONGO_DB",dbname)

        self.mongo = pymongo.MongoClient( host, port=port, username=username,password=password,authSource=dbname,authMechanism="SCRAM-SHA-256" )


    def getClient(self):
        return self.mongo

    @staticmethod
    def setup(host="localhost",port="27017",username="crypto",password="helloworld",dbname="crypto"):
        if MongoWrapper._instance is None:
            MongoWrapper._instance = MongoWrapper(host,port,username,password,dbname)
        else:
            print("WARN: mongowrapper already setup")

        return MongoWrapper._instance


    @staticmethod
    def getInstance():
        if MongoWrapper._instance is None:
            MongoWrapper._instance = MongoWrapper()

        return MongoWrapper._instance


