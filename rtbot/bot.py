# settings.py
import yaml
import time
import logging
import logging.config
import requests
import rt
from functools import partial
from dotenv import load_dotenv
from .alma import Alma
from .rt import Tracker
from .processors import get_processors

with open('logging.yml') as fp:
    logging.config.dictConfig(yaml.load(fp, Loader=yaml.SafeLoader))
log = logging.getLogger(__name__)

# Load environment variables from a .env file
load_dotenv()


def retry_on_error(do_stuff):
    while True:
        try:
            do_stuff()
            break
        except requests.RequestException as ex:
            log.warning('Got requestion exception: %s, will retry in a sec.', ex)
            time.sleep(3)
            # retry
            pass
        except rt.UnexpectedResponse as ex:
            log.warning('Got unexpected response from RT: %s, will retry in a sec.', ex)
            time.sleep(3)
            # retry
            pass
        except rt.ConnectionError as ex:
            log.warning('Connection error while processing: %s, will retry in a sec.', ex)
            time.sleep(3)
            # retry
            pass
        time.sleep(1)


def process_tickets(processor):
    for ticket in processor.get_tickets():
        time.sleep(1)
        retry_on_error(partial(processor.process_ticket, ticket))


def main():
    alma = Alma()
    tracker = Tracker()

    for processor in get_processors(tracker, alma):
        retry_on_error(partial(process_tickets, processor))


if __name__ == '__main__':
    main()

