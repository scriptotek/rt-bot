# settings.py
import yaml
import logging
import logging.config
logging.config.dictConfig(yaml.load(open('logging.yml')))

import functools
from urllib.parse import quote
import re
import os
import time

import requests
import rt
from dotenv import load_dotenv

log = logging.getLogger(__file__)

# Load environment variables from a .env file
load_dotenv()

# General settings
DEFAULT_TIMEOUT = 30

# RT settings
RT_URL = 'https://rt.uio.no/REST/1.0/'
RT_USER = os.getenv('RT_USER')
RT_PASSWORD = os.getenv('RT_PASSWORD')
RT_QUEUE = 'ub-alma'

# Alma settings
ALMA_URL = 'https://api-eu.hosted.exlibrisgroup.com/almaws/v1'
ALMA_KEY = os.getenv('ALMA_KEY')

# Text patterns that will cause RT queue suggestions
pattern_map = {
    'Arkeologisk bibliotek': 'ub-humsam-biblioteket',
    'Etnografisk bibliotek': 'ub-humsam-biblioteket',
    'HumSam-biblioteket': 'ub-humsam-biblioteket',
    'Ibsensenteret': 'ub-ujur',
    'Informatikkbiblioteket': 'ub-realfagsbiblioteket-ifi',
    'Juridisk bibliotek': 'ub-ujur',
    'Kriminologibiblioteket': 'ub-ujur',
    'Læringssenteret DN': 'ub-ujur',
    'Medisinsk bibliotek Odontologi': 'ub-umed',
    'Medisinsk bibliotek Rikshospitalet': 'ub-umed',
    'Medisinsk bibliotek Ullevål sykehus': 'ub-umed',
    'Menneskerettighetsbiblioteket': 'ub-ujur',
    'NSSF Selvmordsforskning og forebygging': 'ub-ujur',
    'Naturhistorisk museum biblioteket': 'ub-realfagsbiblioteket',
    'Offentligrettsbiblioteket': 'ub-ujur',
    'Petroleums- og EU-rettsbiblioteket': 'ub-ujur',
    'Privatrettsbiblioteket': 'ub-ujur',
    'Realfagsbiblioteket': 'ub-realfagsbiblioteket',
    'Rettshistorisk samling': 'ub-ujur',
    'Rettsinformatikkbiblioteket': 'ub-ujur',
    'Sjørettsbiblioteket': 'ub-ujur',
    'Sophus Bugge': 'ub-humsam-biblioteket',
    'Teologisk bibliotek': 'ub-humsam-biblioteket',
}

# Map of library codes to RT queues
libcode_map = {
    '1030011': 'ub-humsam-biblioteket',
    '1030010': 'ub-humsam-biblioteket',
    '1030012': 'ub-humsam-biblioteket',
    '1030300': 'ub-humsam-biblioteket',
    '1030305': 'ub-humsam-biblioteket',
    '1030104': '',
    '1030317': 'ub-realfagsbiblioteket-ifi',
    '1030000': 'ub-ujur',
    '1030002': 'ub-ujur',
    '1030009': 'ub-ujur',
    '1030307': 'ub-umed',
    '1032300': 'ub-umed',
    '1030338': 'ub-umed',
    '1030048': 'ub-ujur',
    '1032304': 'ub-umed',
    '1030500': 'ub-realfagsbiblioteket',
    '1030003': 'ub-ujur',
    '1030005': 'ub-ujur',
    '1030001': 'ub-ujur',
    '1030310': 'ub-realfagsbiblioteket',
    '1030015': 'ub-ujur',
    '1030004': 'ub-ujur',
    '1030006': 'ub-ujur',
    '1030303': 'ub-humsam-biblioteket',
    '1030301': 'ub-humsam-biblioteket',
}

# Create a session for Alma requests, with a default timeout and headers
session = requests.Session()
session.get = functools.partial(session.get, timeout=DEFAULT_TIMEOUT)
session.headers = {
    'Accept': 'application/json',
    'Authorization': 'apikey %s' % ALMA_KEY,
}

# Initialize RT tracker and add a default timeout
tracker = rt.Rt(RT_URL, RT_USER, RT_PASSWORD)
tracker.session.get = functools.partial(tracker.session.get, timeout=DEFAULT_TIMEOUT)
tracker.login()
log.info('RT login OK')


# Suggest a queue based on the owning library of any item barcodes found in the email body.
def suggest_from_alma_items(ticket_id, content):

    barcodes = re.findall(r'\b[0-9a-zA-Z]{9}\b', content)
    barcodes = set([x for x in barcodes if re.search(r'[0-9]{4}', x)])

    for barcode in re.findall(r'\bRS-47BIBSYSUBO[0-9]+\b', content):
        barcodes.add(barcode)

    # log.info('Found %d possible barcodes in this email' % len(barcodes))

    log.info('[#%s] Found %d possible item barcodes', ticket_id, len(barcodes))

    for barcode in barcodes:
        response = session.get(
            '%s/items' % ALMA_URL,
            params={
                'item_barcode': barcode,
            }
        ).json()
        if 'errorsExist' in response:
            log.info('[#%s] Invalid barcode: %s', ticket_id, barcode)
        else:
            # log.info('[#%s] Valid barcode found: %s', ticket_id, barcode)
            # print(response)
            libcode = response['item_data']['library']['value']
            libname = response['item_data']['library']['desc']

            loccode = response['item_data']['location']['value']
            locname = response['item_data']['location']['desc']

            log.info('[#%s] Barcode %s belongs to %s', ticket_id, barcode, libname)

            if libcode not in libcode_map:
                log.warning('Unknown library code: %s', libcode)
            else:
                yield {
                    'queue': libcode_map[libcode],
                    'comment': '- %s hører til %s %s.' % (barcode, libname, locname),
                }


# Suggest a queue based on specific text patterns found the email body.
def suggest_from_pattern_match(ticket_id, content):
    suggest_queue = None
    for pattern, queue in pattern_map.items():
        if re.search(pattern, content):
            log.info('[#%s] Ticket content matched pattern "%s"', ticket_id, pattern)
            yield {
                'queue': queue,
                'comment': '- Meldingen inneholder teksten "%s"' % pattern,
            }


# Suggest a queue based on the resource sharing library of the sender.
def suggest_from_sender(ticket_id, email):
    search_results = session.get(
        '%s/users' % ALMA_URL,
        params={
            'q': 'email~%s' % email,
            'limit': 10,
            'offset': 0
        }
    ).json()

    if search_results['total_record_count'] == 0:
        yield {
            'queue': None,
            'comment': '- Avsenderadressen ble ikke funnet i Alma.',
        }
    else:

        primary_id = search_results['user'][0]['primary_id']
        user_data = session.get('%s/users/%s' % (ALMA_URL, quote(primary_id))).json()
        user_group = user_data['user_group']['desc']
        user_group_code = int(user_data['user_group']['value'])

        if user_group_code >= 8:
            yield {
                'queue': None,
                'comment': '- Avsender (%s) er i brukergruppen «%s».' % (
                    primary_id,
                    user_group
                ),
            }

        elif 'rs_library' in user_data and len(user_data['rs_library']) > 0:
            libcode = user_data['rs_library'][0]['code']['value']
            libname = user_data['rs_library'][0]['code']['desc']
            log.info('[#%s] Sender email %s belongs to Alma user %s with resource sharing library: %s', ticket_id, email, primary_id, libname)

            queue = libcode_map.get(libcode)
            if queue is not None:
                yield {
                    'queue': queue,
                    'comment': '- Avsender (%s) er i brukergruppen «%s» og har %s som resource sharing library.' % (
                        primary_id,
                        user_group,
                        libname
                    ),
                }
        else:
            log.info('[#%s] Sender email %s belongs to Alma user %s, who does not have a resource sharing library configured.', ticket_id, email, primary_id)
            yield {
                'queue': None,
                'comment': '- Avsender (%s) er i brukergruppen «%s» og har ikke noe resource sharing library.' % (
                    primary_id,
                    user_group
                ),
            }


def process_ticket(ticket_id):
    ticket = tracker.get_ticket(ticket_id)

    # Order of preference
    suggestion_order = ['alma_items', 'pattern_match', 'sender_rs']

    suggestions = {x: [] for x in suggestion_order}

    # Get resource sharing library
    requestor_email = ticket['Requestors'][0]
    for suggestion in suggest_from_sender(ticket_id, requestor_email):
        suggestions['sender_rs'].append(suggestion)

    # Loop through attachments and check their content
    for n, att_info in enumerate(tracker.get_attachments(ticket_id)):
        att = tracker.get_attachment(ticket_id, att_info[0])
        content_type = att['ContentType']
        if content_type == 'text/plain':
            content = att['Content'].decode('utf-8')
            for suggestion in suggest_from_alma_items(ticket_id, content):
                suggestions['alma_items'].append(suggestion)
            for suggestion in suggest_from_pattern_match(ticket_id, content):
                suggestions['pattern_match'].append(suggestion)
            break

    # We now have zero or more suggestions. Time to make a decision.
    decision = None
    comments = [];
    for k in suggestion_order:
        for suggestion in suggestions[k]:
            if suggestion['queue'] is not None:
                log.info('[#%s] %s suggestion: %s', ticket_id, k, suggestion['queue'])
                if decision is None:
                    decision = suggestion
            if suggestion['comment'] is not None:
                comments.append(suggestion['comment'])

    if decision is not None:
        comments.insert(0, 'Saken ble automatisk flyttet fra %s til %s basert på følgende informasjon:' % (RT_QUEUE, decision['queue']))
        comments.append('Automatisk sortering er et eksperiment. Si gjerne fra hvis det gjøres feil.')

        comment_body = '\n'.join(comments)
        log.info('[#%s] Conclusion: Move to %s', ticket_id, decision['queue'])
        log.info('[#%s] Comment:\n%s', ticket_id, comment_body)

        # if decision['queue'] != 'ub-realfagsbiblioteket':
        # DRY RUN. STOP HERE!
        # return

        if not tracker.comment(ticket_id, text=comment_body, bcc='d.m.heggo@ub.uio.no'):
            log.error('[#%s] Failed to add comment to ticket!', ticket_id)
            return

        if not tracker.edit_ticket(ticket_id, Queue=decision['queue']):
            log.error('[#%s] Failed to move ticket!', ticket_id)
            return

    else:
        log.info('[#%s] Did not find a suggestion for this ticket.', ticket_id)

    time.sleep(1)

# tickets = [ticket['id'].split('/')[1] for ticket in tracker.search(Queue=RT_QUEUE, Status='new', Owner='nobody')]

search_query={
    'Queue': RT_QUEUE,
    'Status': 'new',
    # 'Id': '3035752',
}
# search = tracker.search(Queue=RT_QUEUE, Status='new')

ticket_ids = [ticket['id'].split('/')[1] for ticket in tracker.search(**search_query)]
log.info('Found %d tickets in %s' % (len(ticket_ids), RT_QUEUE))
for n, ticket_id in enumerate(ticket_ids):
    while True:
        try:
            log.info('[#%s] Processing ticket %d of %d', ticket_id, n + 1, len(ticket_ids))
            process_ticket(ticket_id)
            break
        except requests.RequestException as ex:
            log.warning('[#%s] Got requestion exception: %s, will retry in a sec.', ticket_id, ex)
            time.sleep(3)
            # retry
            pass
        except rt.UnexpectedResponse as ex:
            log.warning('[#%s] Got unexpected response from RT: %s, will retry in a sec.', ticket_id, ex)
            time.sleep(3)
            # retry
            pass
