import re
import rt
import logging
from .processor import Processor

log = logging.getLogger(__name__)


class MergeUiATickets(Processor):
    # Merge tickets from the UiA support system with the same ticket ID

    queries = [
        {
            'Queue': 'ub-brukerhenvendelser',
            'Status': 'new',
        },
    ]

    def merge(self, ticket, into):
        log.info('Merging ticket %d into %d', ticket['id'], into['id'])
        self.rt.merge_ticket(ticket['id'], into['id'])

    def process_ticket(self, ticket):
        m = re.match('.*UiA (INC[0-9]+)', ticket['Subject'])
        if m:
            uia_ticket_id = m.group(1)
            log.info('UiA ticket ID: %s ', uia_ticket_id)

            # Find all tickets with this ticket ID
            tickets = sorted(self.rt.search(Queue=rt.ALL_QUEUES, Subject__like=uia_ticket_id), key=lambda x: x['id'])

            for ticket2 in tickets[1:]:
                self.merge(ticket2, tickets[0])
            return True

        return False
