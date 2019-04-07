import logging
import re
from urllib.parse import quote
from .processor import Processor

log = logging.getLogger(__name__)

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


class AutoSort(Processor):
    # Sort tickets into different RT queues based on a few simple rules.

    queries = [
        {
            'Queue': 'ub-brukerhenvendelser',
            'Status': 'new',
        }
    ]

    def suggest_from_alma_items(self, ticket_id, content):
        # Suggest a queue based on the owning library of any item barcodes found in the email body.
        rule_name = 'alma_items'

        barcodes = re.findall(r'\b[0-9a-zA-Z]{9}\b', content)
        barcodes = set([x for x in barcodes if re.search(r'[0-9]{4}', x)])

        for barcode in re.findall(r'\bRS-47BIBSYSUBO[0-9]+\b', content):
            barcodes.add(barcode)

        log.info('[#%s] Found %d possible item barcodes', ticket_id, len(barcodes))

        for barcode in barcodes:
            response = self.alma.get_json('/items', params={'item_barcode': barcode})
            item_data = response.get('item_data')

            if item_data is None:
                log.info('[#%s] Invalid barcode: %s', ticket_id, barcode)
            else:
                libcode = item_data['library']['value']
                libname = item_data['library']['desc']
                locname = item_data['location']['desc']

                log.info('[#%s] Barcode %s belongs to %s', ticket_id, barcode, libname)

                if libcode not in libcode_map:
                    log.warning('Unknown library code: %s', libcode)
                else:
                    yield {
                        'rule': rule_name,
                        'queue': libcode_map[libcode],
                        'comment': '- %s hører til %s %s.' % (barcode, libname, locname),
                    }

    def suggest_from_pattern_match(self, ticket_id, content):
        # Suggest a queue based on specific text patterns found the email body.
        rule_name = 'pattern_match'
        for pattern, queue in pattern_map.items():
            if re.search(pattern, content):
                log.info('[#%d] Ticket content matched pattern "%s"', ticket_id, pattern)
                yield {
                    'rule': rule_name,
                    'queue': queue,
                    'comment': '- Meldingen inneholder teksten "%s"' % pattern,
                }

    def suggest_from_sender(self, ticket_id, email):
        # Suggest a queue based on the resource sharing library of the sender.

        rule_name = 'rs_library'
        search_results = self.alma.get_json('/users', params={
            'q': 'email~%s' % email,
            'limit': 10,
            'offset': 0,
        })
        if search_results['total_record_count'] == 0:
            yield {
                'rule': rule_name,
                'queue': None,
                'comment': '- Avsenderadressen ble ikke funnet i Alma.',
            }
        else:

            primary_id = search_results['user'][0]['primary_id']
            user_data = self.alma.get_json('/users/%s' % quote(primary_id))
            user_group = user_data['user_group']['desc']
            user_group_code = int(user_data['user_group']['value'])

            if user_group_code >= 8:
                yield {
                    'rule': rule_name,
                    'queue': None,
                    'comment': '- Avsender (%s) er i brukergruppen «%s».' % (
                        primary_id,
                        user_group
                    ),
                }

            elif 'rs_library' in user_data and len(user_data['rs_library']) > 0:
                libcode = user_data['rs_library'][0]['code']['value']
                libname = user_data['rs_library'][0]['code']['desc']
                log.info('[#%s] Sender email %s belongs to Alma user %s with resource sharing library: %s',
                         ticket_id, email, primary_id, libname)

                queue = libcode_map.get(libcode)
                if queue is not None:
                    yield {
                        'rule': rule_name,
                        'queue': queue,
                        'comment': '- Avsender (%s) er i brukergruppen «%s» og har %s som resource sharing library.' % (
                            primary_id,
                            user_group,
                            libname
                        ),
                    }
            else:
                log.info('[#%s] Sender email %s belongs to Alma user %s, who does not have a resource sharing library configured.',
                         ticket_id, email, primary_id)
                yield {
                    'rule': rule_name,
                    'queue': None,
                    'comment': '- Avsender (%s) er i brukergruppen «%s» og har ikke noe resource sharing library.' % (
                        primary_id,
                        user_group
                    ),
                }

    def get_suggestions(self, ticket):
        # Given a ticket id, generate a set of suggestions
        suggestions = []
        requestor_email = ticket['Requestors'][0]

        # Generate suggestions from the resource sharing library of the sender
        for suggestion in self.suggest_from_sender(ticket['id'], requestor_email):
            suggestions.append(suggestion)

        content = self.get_plain_text_content(ticket)
        if content is not None:
            # Generate suggestions from the document barcodes found in the text
            for suggestion in self.suggest_from_alma_items(ticket['id'], content):
                suggestions.append(suggestion)

            # Generate suggestions from pre-defined text pattern matches
            for suggestion in self.suggest_from_pattern_match(ticket['id'], content):
                suggestions.append(suggestion)

        return suggestions

    def make_decision(self, ticket_id, suggestions):
        # Given a set of suggestions, make a decision

        # Order of preference
        rule_preference_order = ['alma_items', 'pattern_match', 'rs_library']

        decision = None
        comments = []
        for k in rule_preference_order:
            matched = [suggestion for suggestion in suggestions if suggestion['rule'] == k]
            for suggestion in matched:
                if suggestion['queue'] is not None:
                    log.info('[#%s] %s suggestion: %s', ticket_id, k, suggestion['queue'])
                    if decision is None:
                        decision = suggestion
                if suggestion['comment'] is not None:
                    comments.append(suggestion['comment'])

        return decision, comments

    def process_ticket(self, ticket):
        suggestions = self.get_suggestions(ticket)

        decision, comments = self.make_decision(ticket['id'], suggestions)

        if decision is not None:
            comments.insert(0, '🚚 Saken ble automatisk flyttet fra %s til %s basert på følgende informasjon:' % (ticket['Queue'], decision['queue']))
            comments.append('Har scriptet gjort noe feil? Meld fra til Dan Michael.')

            comment_body = '\n'.join(comments)
            log.info('[#%s] Conclusion: Move to %s', ticket['id'], decision['queue'])
            log.info('[#%s] Comment:\n%s', ticket['id'], comment_body)

            # To test without editing, uncomment the line below
            # return

            if not self.rt.comment(ticket['id'], text=comment_body):
                log.error('[#%s] Failed to add comment to ticket!', ticket['id'])
                return False

            if not self.rt.edit_ticket(ticket['id'], Queue=decision['queue']):
                log.error('[#%s] Failed to move ticket!', ticket['id'])
                return False

            return True

        log.info('[#%s] Did not find a suggestion for this ticket.', ticket['id'])
        return False
