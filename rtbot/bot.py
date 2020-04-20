# settings.py
import yaml
import time
import logging.config
import requests
import rt
import backoff
from dotenv import load_dotenv
from .alma import Alma
from .rt import Tracker
from .processors import get_processors

with open('logging.yml') as fp:
    logging.config.dictConfig(yaml.load(fp, Loader=yaml.SafeLoader))
log = logging.getLogger(__name__)

# Load environment variables from a .env file
load_dotenv()

exceptions = (
    requests.exceptions.Timeout,
    requests.exceptions.ConnectionError,
    requests.exceptions.RequestException,
    rt.UnexpectedResponse,
)


@backoff.on_exception(backoff.expo, exceptions, max_tries=10)
def process_ticket(processor, ticket):
    processor.process_ticket(ticket)


@backoff.on_exception(backoff.expo, exceptions, max_tries=10)
def process_tickets(processor):
    for ticket in processor.get_tickets():
        time.sleep(1)
        process_ticket(processor, ticket)


def main():
    alma = Alma()
    tracker = Tracker()

    for processor in get_processors(tracker, alma):
        process_tickets(processor)


if __name__ == '__main__':
    main()

