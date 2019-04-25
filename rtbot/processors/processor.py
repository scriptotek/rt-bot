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

