import logging

log = logging.getLogger(__name__)


class Processor():
    def __init__(self, rt, alma):
        self.rt = rt
        self.alma = alma
