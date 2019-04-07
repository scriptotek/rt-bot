import logging
import os
import requests
import functools

log = logging.getLogger(__name__)

# General settings
DEFAULT_TIMEOUT = 30
ALMA_URL = 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1'


class Alma(object):

    def __init__(self):
        # Create a session for Alma requests, with a default timeout and headers
        self.session = requests.Session()
        self.session.get = functools.partial(self.session.get, timeout=DEFAULT_TIMEOUT)
        self.session.headers = {
            'Accept': 'application/json',
            'Authorization': 'apikey %s' % os.getenv('ALMA_KEY'),
        }

    def get_session(self):
        return self.session

    def get(self, url, **kwargs):
        return self.session.get(ALMA_URL + '/' + url.lstrip('/'), **kwargs)

    def get_json(self, url, **kwargs):
        res = self.get(url, **kwargs)

        try:
            return res.json()
        except json.decoder.JSONDecodeError:
            log.error('Could not decode JSON: %s', res.text)
            raise

