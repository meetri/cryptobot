import os,urllib.parse
from twilio.rest import Client

class TwilioSms(object):

    _instance = None

    def __init__(self,sms_from=None,sid=None,token=None):
        self.sms_from = os.getenv("TWILIO_FROM",sms_from).strip()
        if not self.sms_from.startswith("+"):
            self.sms_from = "+{}".format(self.sms_from)

        sid = os.getenv("TWILIO_SID",sid)
        token = os.getenv("TWILIO_TOKEN",token)
        self.client = Client(sid, token)
        # print("twilio_from: '{}'".format(self.sms_from))
        # print("twilio_sid: '{}'".format(sid))
        # print("twilio_token: '{}'".format(token))

    @staticmethod
    def getInstance():
        if TwilioSms._instance is None:
            TwilioSms._instance = TwilioSms()
        return TwilioSms._instance


    def send( self,msg, number):
        numlist = number.split(",")
        for num in numlist:
            num = num.strip()
            if not num.startswith("+"):
                num = "+{}".format(num)
            message = self.client.messages.create(to=num, from_= self.sms_from , body=msg)

