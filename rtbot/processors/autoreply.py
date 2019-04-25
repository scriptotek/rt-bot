import re
import logging
from .processor import Processor

log = logging.getLogger(__name__)


class ResolveAutoReplies(Processor):
    # Auto-resolve automatic reply tickets

    queries = [
        {
            'Queue': 'ub-brukerhenvendelser',
            'Status': 'new',
        },
        {
            'Queue': 'ub-humsam-biblioteket',
            'Status': 'new',
        },
        {
            'Queue': 'ub-realfagsbiblioteket',
            'Status': 'new',
        }
    ]

    def process_ticket(self, ticket):
        match = re.search('automatic reply', ticket['Subject'], re.I)
        if match is not None:
            log.info('[#%s] Auto-resolving ticket with subject: %s',
                     ticket['id'], ticket['Subject'])
            if not self.rt.edit_ticket(ticket['id'], Status='resolved'):
                log.error('[#%s] Failed to auto-resolve ticket!', ticket['id'])
                return False
            return True
