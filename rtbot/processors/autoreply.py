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

    def autoresolve(self, ticket, category, reason):
        log.info('[#%s] Auto-resolving ticket with subject: %s',
                    ticket['id'], ticket['Subject'])

        comment = "<p>Meldingen ble klassifisert som <strong>%s</strong> fordi %s.<p><p>Saken ble derfor automatisk lukket av rt-bot-modulen " % (category, reason) + \
            "<a href='https://github.com/scriptotek/rt-bot/blob/master/rtbot/processors/autoreply.py'>autoreply.py</a>.</p>" + \
            "<p>Ble meldingen feilklassifisert? Gi beskjed til Dan Michael.</p>"
        if not self.rt.comment(ticket['id'], text=comment, content_type='text/html'):
            log.error('[#%s] Failed to add comment to ticket!', ticket['id'])
            return False
        if not self.rt.edit_ticket(ticket['id'], Status='resolved'):
            log.error('[#%s] Failed to auto-resolve ticket!', ticket['id'])
            return False
        return True

    def process_ticket(self, ticket):
        sender_email = ticket['Requestors'][0]

        if re.search(r'(automatic reply|automatisk svar)', ticket['Subject'], re.I):
            return self.autoresolve(
                ticket,
                "generelt autosvar",
                "meldingens emne inneholder teksten «automatic reply» eller «automatisk svar»"
            )

        if re.search(r'Re: UiA INC.*- Notification Item Letter', ticket['Subject']):
            return self.autoresolve(
                ticket,
                "autosvar fra UiA på Alma Notification Item Letter",
                "meldingens emne inneholdt teksten «Re: UiA INC*- Notification Item Letter»"
            )

        if re.search(r'Notification Item Letter', ticket['Subject']) and sender_email == 'noreply@topdesk.net':
            return self.autoresolve(
                ticket,
                "autosvar fra UBB på Alma Notification Item Letter",
                "meldingens emne inneholdt teksten «Notification Item Letter» og avsender var noreply@topdesk.net"
            )
