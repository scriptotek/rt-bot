# settings.py
import yaml
import time
import logging
import logging.config
import requests
import rt
from dotenv import load_dotenv
from .alma import Alma
from .rt import Tracker
from .processors import get_processors

with open('logging.yml') as fp:
    logging.config.dictConfig(yaml.load(fp, Loader=yaml.SafeLoader))
log = logging.getLogger(__name__)

# Load environment variables from a .env file
load_dotenv()


def main():
    alma = Alma()
    tracker = Tracker()

    search_query={
        'Queue': 'ub-brukerhenvendelser',
        'Status': 'new',
    }

    processors = get_processors(tracker, alma)

    tickets = list(tracker.search(search_query))
    log.info('Found %d tickets having %s', len(tickets),
             ' AND '.join(['%s=%s' % (k, v) for k, v in search_query.items()]))

    for n, ticket in enumerate(tickets):
        for processor in processors:
            while True:
                try:
                    log.info('[#%s] Processing ticket %d of %d using %s processor',
                             ticket['id'], n + 1, len(tickets), type(processor).__name__)
                    processed = processor.process_ticket(ticket)
                    break
                except requests.RequestException as ex:
                    log.warning('[#%s] Got requestion exception: %s, will retry in a sec.', ticket['id'], ex)
                    time.sleep(3)
                    # retry
                    pass
                except rt.UnexpectedResponse as ex:
                    log.warning('[#%s] Got unexpected response from RT: %s, will retry in a sec.', ticket['id'], ex)
                    time.sleep(3)
                    # retry
                    pass
            if processed is True:
                break
        time.sleep(1)


if __name__ == '__main__':
    main()

