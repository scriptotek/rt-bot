import pydash
import logging
import re
from typing import Optional
import requests
from .processor import Processor

log = logging.getLogger(__name__)


pickup_points = {
    'Humanities and Social Sciences Library (GSH)': 'ub-humsam-biblioteket',
    'Law Library (Domus Juridica)': 'ub-ujur',
    'Medical Library (Rikshospitalet)': 'ub-umed',
    'Science Library (VB)': 'ub-realfagsbiblioteket',
    'HumSam-biblioteket (GSH)': 'ub-humsam-biblioteket',
    'Juridisk bibliotek (Domus Juridica)': 'ub-ujur',
    'Medisinsk bibliotek (Rikshospitalet)': 'ub-umed',
    'Realfagsbiblioteket (VB)': 'ub-realfagsbiblioteket',
}


class TakeAway(Processor):
    # Sort tickets into different RT queues based on dropdown selection from Nettskjema.

    queries = [
        {
            'Queue': 'ub-brukerhenvendelser',
            'Status': 'new',
        }
    ]

    def lookup_alma_user(self, feide_id, sender_email=None):
        if feide_id is None:
            return None
        try:
            res = self.alma.get_json('/users/%s' % feide_id)
            if res.get('errorsExist'):
                log.info('User not found in Alma: %s', feide_id)
            else:
                log.info('User found in Alma: %s', feide_id)
                return {
                    'lang': pydash.get(res, 'preferred_language.desc'),
                    'user_group': pydash.get(res, 'user_group.desc'),
                    'primary_id': pydash.get(res, 'primary_id'),
                    'rs_library': pydash.get(res, 'rs_library.code.0.desc'),
                }
        except:
            pass

        if sender_email is not None:
            try:
                res = self.alma.get_json('/users', params={'q': 'ALL~%s' % sender_email})
                if res['total_record_count'] == '0':
                    log.info('User not found in Alma: %s', sender_email)
                else:
                    log.info('User found in Alma: %s', sender_email)
                    user_id = pydash.get(res, 'user.0.primary_id')
                    return self.lookup_alma_user(user_id)
            except:
                pass

        return None

    def lookup_alma_item(self, isbn):
        if isbn is None:
            return None
        res = requests.get('https://ub-lsm.uio.no/alma/search', params={
            'query': 'alma.isbn=' + isbn,
        }).json()

        if not pydash.get(res, 'results.0.holdings.0'):
            log.info('Zero results in Alma for IBSN: %s' % isbn)
            return None

        out = f'📙 Holdings for ISBN {isbn}:\n<ul>'
        for bib in pydash.get(res, 'results'):
            title = bib.get('title')
            for holding in bib.get('holdings'):
                tot = int(holding.get('total_items'))
                unav = int(holding.get('unavailable_items'))
                out += '<li>%s %s' % (holding.get('location', '-'), holding.get('callcode', '-'))
                out += ': %d of %d available</li>\n' % (tot - unav, tot)

        out += '</ul>'
        return out

    @staticmethod
    def determine_queue(content: str) -> Optional[str]:
        # Determine queue from email body.
        for pickup_point, queue in pickup_points.items():
            if content.find(f'    * {pickup_point}') != -1:
                return queue

    @staticmethod
    def extract_email(content: str) -> Optional[str]:
        # Determine requestor e-mail from email body.
        m = re.search(r'    \* (.+?@.+?\.[a-z]{2,3})$', content, re.MULTILINE)
        if not m:
            return None
        return m.group(1)

    @staticmethod
    def extract_isbns(content: str) -> Optional[str]:
        # Determine requestor e-mail from email body.
        content = content.replace('-', '')
        return re.findall(r'\b(97[0-9]{11}|[1-9][0-9]{9})\b', content, re.MULTILINE)

    def process_ticket(self, ticket: dict):

        if re.match('Submission to .+ has been delivered', ticket['Subject']) is None:
            return False

        log.info('[#%s] From Nettskjema', ticket['id'])

        content = self.get_plain_text_content(ticket)
        if content is None:
            return False

        queue = self.determine_queue(content)
        if queue is None:
            log.warning('[#%s] Could not determine queue!', ticket['id'])
            return False
        log.info('[#%s] Queue: %s', ticket['id'], queue)

        comment_body = []

        # Lookup sender in Alma

        feide_id = self.extract_email(content)
        sender_email = ticket['Requestors'][0]
        alma_user = self.lookup_alma_user(feide_id, sender_email)
        if alma_user is not None:
            comment_body.append(
                '😊 Informasjon om bestiller:\n<ul>' +
                '<li>Primær-ID: %s</li>\n' % alma_user['primary_id'] +
                '<li>Brukergruppe: %s</li>\n' % alma_user['user_group'] +
                '<li>Resource sharing library: %s</li>\n' % alma_user['rs_library'] +
                '<li>Foretrukket språk: %s</li>\n' % alma_user['lang'] +
                '</ul>\n'
            )
        else:
            comment_body.append(
                '😲 Klarte ikke å automatisk finne bestiller i Alma ved søk på «%s» eller «%s».' % (feide_id, sender_email)
            )

        # Lookup requested material

        if content.find('    * Ja\n') != -1:
            log.info('Request includes specific isbn(s)')
            for isbn in self.extract_isbns(content):
                alma_item = self.lookup_alma_item(isbn)
                if alma_item is None:
                    log.info('Not found in alma: %s', isbn)
                else:
                    log.info('Found in alma: %s', isbn)
                    comment_body.append(alma_item)

        if len(comment_body):
            if not self.rt.comment(ticket['id'], text='\n'.join(comment_body), content_type='text/html'):
                log.error('[#%s] Failed to add comment to ticket!', ticket['id'])
                return False

        if not self.rt.edit_ticket(ticket['id'], Queue=queue, Subject='UiO Library takeaway request'):
            log.error('[#%s] Failed to update ticket!', ticket['id'])
            return False

        self.rt.reply(ticket['id'], 'Your takeaway request has been received. You will receive a new e-mail once it\'s ready.')

        return True
