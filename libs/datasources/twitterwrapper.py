import os,twitter

class TwitterWrapper(object):

    _instance = None

    def __init__(self):
        self.api = twitter.Api(**{
                "consumer_key": os.getenv("TWITTER_CONSUMER_KEY",""),
                "consumer_secret": os.getenv("TWITTER_CONSUMER_SECRET",""),
                "access_token_key": os.getenv("TWITTER_ACCESS_TOKEN_KEY",""),
                "access_token_secret": os.getenv("TWITTER_ACCESS_TOKEN_SECRET",""),
                    })


    def getClient(self):
        return self.api


    @staticmethod
    def getInstance():
        if TwitterWrapper._instance is None:
            TwitterWrapper._instance = TwitterWrapper()

        return TwitterWrapper._instance


