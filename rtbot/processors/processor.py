import logging

log = logging.getLogger(__name__)


class Processor():

    queries = []

    def __init__(self, rt, alma):
        self.rt = rt
        self.alma = alma

    def get_tickets(self):
        for query in self.queries:
            log.info('[%s] Searching for %s',
                     type(self).__name__,
                     ' AND '.join(['%s=%s' % (k, v) for k, v in query.items()]))
            for ticket in self.rt.search(query):
                yield ticket

    def get_plain_text_content(self, ticket):
        # Loop through attachments and check their content
        for n, att_info in enumerate(self.rt.get_attachments(ticket['id'])):
            att = self.rt.get_attachment(ticket['id'], att_info[0])
            if att['ContentType'] == 'text/plain':
                return att['Content'].decode('utf-8')
