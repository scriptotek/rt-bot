# settings.py
import yaml
import json
import logging
import logging.config
logging.config.dictConfig(yaml.load(open('logging.yml')))

import functools
from urllib.parse import quote
import re
import os
import time

import requests
import rt
from dotenv import load_dotenv

log = logging.getLogger(__file__)

# Load environment variables from a .env file
load_dotenv()

# General settings
DEFAULT_TIMEOUT = 30

# RT settings
RT_URL = 'https://rt.uio.no/REST/1.0/'
RT_USER = os.getenv('RT_USER')
RT_PASSWORD = os.getenv('RT_PASSWORD')
RT_QUEUE = 'ub-realfagsbiblioteket'

# Initialize RT tracker and add a default timeout
tracker = rt.Rt(RT_URL, RT_USER, RT_PASSWORD)
tracker.session.get = functools.partial(tracker.session.get, timeout=DEFAULT_TIMEOUT)
tracker.login()
log.info('RT login OK')

search_query = {
    'Queue': RT_QUEUE,
    'Status': 'new',
    'Owner': 'nobody',
}

ticket_ids = [ticket['id'].split('/')[1] for ticket in tracker.search(**search_query)]

data = {
    RT_QUEUE: len(ticket_ids)
}
log.info('Found %d tickets in %s' % (len(ticket_ids), RT_QUEUE))

with open('public/status.json', 'w') as fp:
    json.dump(data, fp)

