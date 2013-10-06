from pynab.db import db, Collection

class Regex(Collection):
    _collection = 'regexes'

    def __init__(self, _id=None, group_name='', regex='', ordinal=0, status=0, description='', category_id=None, **kwargs):
        self.id = _id
        self.group_name = group_name
        self.regex = regex
        self.ordinal = ordinal
        self.status = status
        self.description = description
        self.category_id = category_id