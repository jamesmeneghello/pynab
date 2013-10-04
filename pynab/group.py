from pynab.db import db, Collection

class Group(Collection):
    _collection = 'groups'

    def __init__(self, name='', min_files=0, min_size=0, active=True, **kwargs):
        self.name = name
        self.min_files = min_files
        self.min_size = min_size
        self.active = active