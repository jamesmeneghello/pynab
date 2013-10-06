from pynab import log
from pynab.db import db, Collection
from pymongo import errors
from pynab.segment import Segment


class Part(Collection):
    _collection = 'parts'

    def __init__(self, subject='', posted=None, posted_by='', group_name='', xref='', total_segments=0, segments=list(), _id='', **kwargs):
        self.id = _id
        self.subject = subject
        self.posted = posted
        self.posted_by = posted_by
        self.group_name = group_name
        self.xref = xref
        self.total_segments = total_segments
        self.segments = segments

    def save(self):
        if self.id:
            query = {'id': self.id}
        else:
            query = {
                'subject': self.subject
            }
        p = Part.get_one(**query)

        if p:
            # merge segments with existing sets, since mongo doesn't support
            # addToSet for nested arrays of arrays of arrays of arrays of...
            self.segments = list(set(p.segments + self.segments))

        self._save()

    def _save(self):
        try:
            self.id = db.parts.find_and_modify(
                {
                    'subject': self.subject
                },
                {
                    '$setOnInsert': {'posted': self.posted},
                    '$set': {
                        'posted_by': self.posted_by,
                        'group_name': self.group_name,
                        'total_segments': self.total_segments,
                        'xref': self.xref,
                        'segments': [s.dict() for s in self.segments]
                    }
                },
                new=True,
                upsert=True
            ).get('_id')
            return True
        except errors.OperationFailure as e:
            log.error(e)
            return False

    def delete(self):
        if self.id:
            query = {'_id': self.id}
        else:
            query = {'subject': self.subject}
        try:
            db[self._collection].remove(query)
            return True
        except errors.OperationFailure as e:
            log.error(e)
            return False

    def size(self):
        total = 0
        for segment in self.segments:
            total += segment.size

        return total

    def dict(self):
        return dict(
            id=self.id,
            subject=self.subject,
            posted=self.posted,
            posted_by=self.posted_by,
            group_name=self.group_name,
            xref=self.xref,
            total_segments=self.total_segments,
            segments=[s.dict() for s in self.segments]
        )

    def is_blacklisted(self):
        # TODO: blacklists
        pass

    def post_get(self):
        # pycharm got this one wrong
        self.segments = [Segment(**s) for s in self.segments]
