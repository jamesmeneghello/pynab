from pynab.db import Collection

class Segment(Collection):
    _collection = 'segments'

    def __init__(self, message_id='', segment=0, size=0, _id=None, **kwargs):
        self.id = _id
        self.message_id = message_id
        self.segment = segment
        self.size = size

    def dict(self):
        return dict(
            message_id=self.message_id,
            segment=self.segment,
            size=self.size
        )