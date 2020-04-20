import logging
from .processor import Processor

log = logging.getLogger(__name__)


class ResolveCccReceipts(Processor):
    # Auto-resolve tickets from no-reply@copyright.com and
    # set custom property CccGetItNow=Ja on them.

    queries = [
        {
            'Queue': 'ub-brukerhenvendelser',
            'Status': 'new',
        }
    ]

    def process_ticket(self, ticket):
        if ticket['Requestors'][0] == 'no-reply@copyright.com':
            log.info('[#%s] Updating CCC ticket', ticket['id'])
            if not self.rt.edit_ticket(ticket['id'], Status='resolved', CF_CccGetItNow='Ja'):
                log.error('[#%s] Failed to update ticket!', ticket['id'])
                return False
            return True
