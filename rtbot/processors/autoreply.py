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
        match = re.search('(automatic reply|automatisk svar)', ticket['Subject'], re.I)
        if match is not None:
            log.info('[#%s] Auto-resolving ticket with subject: %s',
                     ticket['id'], ticket['Subject'])
            if not self.rt.comment(ticket['id'], text='🏝 Saken ble automatisk lukket av rt-bot som autosvar. Spørsmål om scriptet? Kontakt Dan Michael.'):
                log.error('[#%s] Failed to add comment to ticket!', ticket['id'])
                return False
            if not self.rt.edit_ticket(ticket['id'], Status='resolved'):
                log.error('[#%s] Failed to auto-resolve ticket!', ticket['id'])
                return False
            return True
