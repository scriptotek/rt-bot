import pydash
import logging
import re
import sys
import time
import json
from typing import Optional
import requests
from datetime import datetime
import sqlite3
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


def create_table() -> None:
    conn = sqlite3.connect('takeaway_stats.db')
    cur = conn.cursor()
    cur.execute('''CREATE TABLE daily
        (
            request_date text,
            request_code text,
            selected_lib text,
            request_count integer,
            isbn_count integer
        )'''
    )
    cur.execute('''CREATE TABLE requests
        (
            request_prefix text,
            request_prefix_no int,
            request_time text,
            language text,
            selected_lib text,
            rs_lib text,
            user_group text,
            with_isbn text,
            isbn_count integer,
            isbn_bibs text,
            code_prefix text,
            code_no int
        )'''
    )
    conn.commit()
    conn.close()


# create_table()


def add_to_stats(
        request_code_prefix: str,
        request_date: str,
        request_queue: str,
        request_lang: Optional[str],
        user_rs_library: Optional[str],
        user_group: Optional[str],
        has_isbn: bool,
        isbn_count: int,
        isbn_matching_libs: list
) -> str:
    now = datetime.now().strftime('%Y-%m-%d')
    conn = sqlite3.connect('takeaway_stats.db')
    cur = conn.cursor()

    cur.execute("SELECT MAX(code_no) FROM requests WHERE code_prefix = ?", [
        request_code_prefix,
    ])
    rows = cur.fetchall()
    request_code_no = int(rows[0][0] or 0) + 1
    request_code = request_code_prefix + '-%03d' % request_code_no

    # Insert a row of data
    cur.execute("INSERT INTO requests (code_prefix, code_no, request_time, language, selected_lib, rs_lib, user_group, with_isbn, isbn_count, isbn_bibs) VALUES (?,?,?,?,?,?,?,?,?,?)", [
        request_code_prefix,
        request_code_no,
        request_date,
        request_lang,
        request_queue,
        user_rs_library,
        user_group,
        '1' if has_isbn else '0',
        isbn_count,
        json.dumps(isbn_matching_libs)
    ])
    conn.commit()

    cur.execute("SELECT request_count, isbn_count FROM daily WHERE request_date = ? AND selected_lib = ?", [
        now,
        request_queue,
    ])
    rows = cur.fetchall()
    if len(rows) != 0:
        request_count = int(rows[0][0]) + 1
        isbn_count = int(rows[0][1]) + isbn_count
        cur.execute("UPDATE daily SET request_count=?, isbn_count=? WHERE request_date = ? AND selected_lib = ?", [
            request_count,
            isbn_count,
            now,
            request_queue,
        ])
        conn.commit()
    else:
        cur.execute("INSERT INTO daily (request_date, selected_lib, request_count, isbn_count) VALUES (?,?,?,?)", [
            now,
            request_queue,
            1,
            isbn_count,
        ])
        conn.commit()

    conn.close()

    return request_code


class TakeAway(Processor):
    # Sort tickets into different RT queues based on dropdown selection from Nettskjema.

    queries = [
        {
            'Queue': 'ub-brukerhenvendelser',
            'Status': 'new',
        }
    ]

    def lookup_alma_user(self, feide_id: Optional[str], sender_email: str = None) -> Optional[dict]:
        if feide_id is None:
            return None
        try:
            res = self.alma.get_json('/users/%s' % feide_id)
            if res.get('errorsExist'):
                log.info('User not found in Alma: %s', feide_id)
            else:
                log.info('User found in Alma: %s', feide_id)
                # print(res)
                return {
                    'lang': pydash.get(res, 'preferred_language.desc'),
                    'user_group': pydash.get(res, 'user_group.desc'),
                    'primary_id': pydash.get(res, 'primary_id'),
                    'rs_library': pydash.get(res, 'rs_library.0.code.desc'),
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

    def lookup_alma_item(self, isbn: str) -> dict:
        res = requests.get('https://ub-lsm.uio.no/alma/search', params={
            'query': 'alma.isbn=' + isbn,
            'expand_items': 'true',
        }).json()

        if not pydash.get(res, 'results.0.holdings.0') and not pydash.get(res, 'results.0.portfolios.0'):
            log.info('Zero results in Alma for IBSN: %s' % isbn)
            yield {
                'bib_id': '',
                'title': 'Ingen treff i Alma',
                'isbn': isbn,
                'holdings': [],
                'portfolios': [],
                'libs': set(),
            }
            return

        log.info('ISBN found in alma: %s', isbn)

        for bib in pydash.get(res, 'results'):
            out = {
                'bib_id': bib['id'],
                'title': bib.get('title', '-'),
                'isbn': isbn,
                'holdings': [],
                'portfolios': [],
                'libs': set(),
            }
            for holding in bib.get('holdings', []):
                tot = int(holding.get('total_items', 0))
                unav = int(holding.get('unavailable_items', 0))
                ava = tot - unav
                if holding.get('library') and ava > 0:
                    out['libs'].add(holding.get('library'))
                out['holdings'].append(self.format_holding(holding, ava, tot))
            for portfolio in bib.get('portfolios', []):
                if portfolio.get('activation') == 'Available':
                    out['portfolios'].append(self.format_portfolio(portfolio))

            yield out

    @staticmethod
    def format_holding(holding: dict, ava: int, tot: int) -> str:
        out = ['<li>']
        out.append('%s %s %s' % (holding.get('library_name', '-'), holding.get('location', '-'), holding.get('callcode', '-')))
        out.append(': <strong>%d</strong> av <strong>%d</strong> tilgjengelig<br>' % (ava, tot))
        barcodes = []
        for item in holding.get('items', []):
            if pydash.get(item, 'base_status.value') == '1':
                barcodes.append(item.get('barcode', ''))
        out.append(' ∙ '.join(barcodes))
        out.append('</li>')
        return '\n'.join(out)

    @staticmethod
    def format_portfolio(portfolio: dict) -> str:
        out = ['<li>']
        out.append('E-book %s from %s<br>' % (portfolio.get('activation', '-'), portfolio.get('collection_name', '-')))
        out.append('</li>')
        return '\n'.join(out)

    @staticmethod
    def format_bib_results(results: list) -> str:
        by_bib: dict = {}
        for res in results:
            if res['bib_id'] not in by_bib:
                by_bib[res['bib_id']] = {
                    'isbns': [res['isbn']],
                    'title': res['title'],
                    'holdings': res['holdings'],
                    'portfolios': res['portfolios'],
                    'libs': res['libs'],
                }

        out = ['<ul>']
        for bib_id, bib in by_bib.items():
            out.append('<li>')
            out.append('📙 ISBN %s: <em>%s</em>' % (' / '.join(bib['isbns']), bib['title']))
            if len(bib['holdings']):
                out.append('<ul>')
                for holding in bib['holdings']:
                    out.append(holding)
                for portfolio in bib['portfolios']:
                    out.append(portfolio)
                out.append('</ul>')
            out.append('</li>')

        out.append('</ul>')
        return '\n'.join(out)

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
    def extract_language(content: str) -> Optional[str]:
        m = re.search(r'    \* (Norsk bokmål|Norsk nynorsk|English)$', content, re.MULTILINE)
        if not m:
            return None
        return m.group(1)

    @staticmethod
    def extract_isbns(content: str) -> list:
        # Extract ISBNs from the last part of the mail body
        # Remove first part to avoid match on phone numbers, which can be 10 digit with country prefix
        content = re.split('ISBN.(?:nummer|number)', content, 1)[1]

        content = content.replace('-', '')
        return re.findall(r'\b(97[0-9xX]{11}|[0-9xX]{10})\b', content, re.MULTILINE)

    def process_ticket(self, ticket: dict) -> bool:

        if re.match('Submission to .+ has been delivered', ticket['Subject']) is None:
            return False

        log.info('[#%s] New take away request', ticket['id'])

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

        rt_language = self.extract_language(content) or 'Ukjent'

        feide_id = self.extract_email(content)

        # print(ticket['FirstRequestor'])
        # sender_name = ticket['FirstRequestor']['RealName']
        # name_prefix = sender_name.split(' ').pop()[:3].upper()

        sender_email = ticket['FirstRequestor']['EmailAddress']

        alma_user = self.lookup_alma_user(feide_id, sender_email)
        if alma_user is not None:
            comment_body.append(
                '<p>👤 Bestiller ble funnet i Alma:</p>\n<ul>' +
                '<li>Primær-ID: %s</li>' % alma_user['primary_id'] +
                '<li>Brukergruppe: %s</li>' % alma_user['user_group'] +
                '<li>Resource sharing library: %s</li>' % alma_user['rs_library'] +
                '<li>Foretrukket språk: %s</li>' % alma_user['lang'] +
                '</ul>'
            )
        else:
            comment_body.append(
                '<p>👤 Klarte ikke å automatisk finne bestiller i Alma ved søk på «%s» eller «%s».</p>' % (feide_id, sender_email)
            )
            alma_user = {
                'user_group': None,
                'rs_library': None,
            }

        # Lookup requested material

        has_isbn = re.search('    \\* (Ja|Yes)\n', content) is not None
        isbns: list = []
        isbn_libnrs = set()
        alma_results = []

        comment_body.append(
            '<p>📚 Dokumenter funnet i Alma:</p>'
        )
        if has_isbn:
            isbns = self.extract_isbns(content)
            for isbn in isbns:
                for alma_result in self.lookup_alma_item(isbn):
                    alma_results.append(alma_result)
                    for libnr in alma_result['libs']:
                        isbn_libnrs.add(libnr)

        log.info('Resultater funnet i følgende bibliotek: %s', ', '.join(list(isbn_libnrs)))

        if len(alma_results) == 0:
            comment_body.append(
                '<ul><li>Ikke funnet automatisk. Se informasjon fra bestiller i meldingen over.</li></ul>'
            )

        comment_body.append(self.format_bib_results(alma_results))

        request_code_prefix = '%s' % datetime.now().strftime('%d')
        request_code = add_to_stats(
            request_code_prefix=request_code_prefix,
            request_date=ticket['Created'],
            request_lang=rt_language,
            request_queue=queue,
            user_rs_library=alma_user['rs_library'],
            user_group=alma_user['user_group'],
            has_isbn=has_isbn,
            isbn_count=len(isbns),
            isbn_matching_libs=list(isbn_libnrs)
        )

        if len(comment_body):
            print(comment_body)
            time.sleep(10)
            if not self.rt.comment(ticket['id'], text='\n'.join(comment_body), content_type='text/html'):
                log.error('[#%s] Failed to add comment to ticket!', ticket['id'])
                return False

        if not self.rt.edit_ticket(ticket['id'], Queue=queue, Subject='UiO Library takeaway request %s' % request_code):
            log.error('[#%s] Failed to update ticket!', ticket['id'])
            return False

        # time.sleep(30)
        return True
