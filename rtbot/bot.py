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

    for processor in get_processors(tracker, alma):
        for ticket in processor.get_tickets():
            while True:
                try:
                    processor.process_ticket(ticket)
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
                except rt.ConnectionError as ex:
                    log.warning('[#%s] Connection error while processing: %s, will retry in a sec.', ticket['id'], ex)
                    time.sleep(3)
                    # retry
                    pass
            time.sleep(1)


if __name__ == '__main__':
    main()

