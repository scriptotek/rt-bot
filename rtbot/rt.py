import logging
import rt
import functools
import os
from .util import process_id

log = logging.getLogger(__name__)

# General settings
DEFAULT_TIMEOUT = 30


class Tracker(object):

    def __init__(self):

        # RT settings
        RT_URL = 'https://rt.uio.no/REST/1.0/'
        RT_USER = os.getenv('RT_USER')
        RT_PASSWORD = os.getenv('RT_PASSWORD')

        # Initialize RT tracker and add a default timeout
        self.tracker = rt.Rt(RT_URL, RT_USER, RT_PASSWORD)
        self.tracker.session.get = functools.partial(self.tracker.session.get, timeout=DEFAULT_TIMEOUT)
        if self.tracker.login():
            log.debug('RT login OK')
        else:
            log.error('RT login failed')
            sys.exit(1)

    def get_tracker(self):
        return self.tracker

    def search(self, query):
        for ticket in self.tracker.search(**query):
            ticket['id'] = process_id(ticket['id'])
            yield ticket

    def __getattr__(self, name):
        def method(*args, **kwargs):
            return getattr(self.tracker, name)(*args, **kwargs)
        return method
