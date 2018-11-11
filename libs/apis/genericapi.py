import os
import requests
import json
from urllib.parse import urlparse
from urllib.parse import urljoin


class GenericApi(object):

    def __init__(self, config):

        self.timeout = 4
        self.api_root = config.get("apiroot")

        self.response = None
        self.data = None

        self.headers = {
            "Content-Type": "application/json",
        }

    def process(self, api_path, payload=None, method=None):

        api_root = self.api_root
        uri = urljoin(api_root, api_path)

        if method is None and payload is not None:
            method = "post"
        elif method is None:
            method = "get"

        if method == "get" and payload is not None:
            params = ""
            for k in payload:
                if len(params) > 0:
                    params += "&"
                params += "{}={}".format(k, payload[k])
            if len(params) > 0:
                params = "?{}".format(params)
                uri = urljoin(uri, params)


        if method == "get":
            self.response = requests.get(uri, headers = self.headers, timeout=self.timeout)
        else:
            self.response = requests.post(uri, data=json.dumps(payload), headers=self.headers, timeout=self.timeout)

        self.response.raise_for_status()
        self.data = self.response.json()

        return self


