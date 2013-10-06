import time
import re
import pytz
import datetime
from pynab import log
from pynab.db import db, Collection
from pynab.group import Group
from pynab.regex import Regex
from pynab.part import Part

class Release(Collection):
    _collection = 'releases'

    def __init__(self, name='', search_name=None, total_binaries = 0, binaries = list(), size = 0,
        posted = '', posted_by = '', completion = 0, grabs = 0, passworded = 0, file_count = 0,
        spotnab_id = 0, group_id = None, category_id = None, regex_id = None, req_id = '',
        tvrage = None, tvdb = None, imdb = None, _id=None, **kwargs):

        self.id = _id
        self.name = name
        self.search_name = search_name
        self.posted = posted
        self.posted_by = posted_by

        self.total_binaries = total_binaries
        self.binaries = binaries
        self.size = size
        self.completion = completion

        self.spotnab_id = spotnab_id
        self.group_id = group_id
        self.category_id = category_id
        self.regex_id = regex_id
        self.req_id = req_id

        self.grabs = grabs
        self.passworded = passworded
        self.file_count = file_count

        self.tvrage = tvrage
        self.tvdb = tvdb
        self.imdb = imdb

    def save(self):
        if self.id:
            match_query = {'_id': self.id}
        else:
            match_query = {'name': self.name}

        db[self._collection].find_and_modify(
            query=match_query,
            update={
                '$set': {
                    'name': self.name,
                    'search_name': self.search_name,
                    'posted': self.posted,
                    'posted_by': self.posted_by,

                    'total_binaries': self.total_binaries,
                    'size': self.size,
                    'completion': self.completion,

                    'spotnab_id': self.spotnab_id,
                    'group_id': self.group_id,
                    'category_id': self.category_id,
                    'regex_id': self.regex_id,
                    'req_id': self.req_id,

                    'grabs': self.grabs,
                    'passworded': self.passworded,
                    'file_count': self.file_count,

                    'tvrage': self.tvrage,
                    'tvdb': self.tvdb,
                    'imdb': self.imdb,
                },
                '$addToSet': {
                    'parts': [b.dict() for b in self.binaries]
                }
            },
            upsert=True
        )

    @classmethod
    def process(cls):
        log.info('Starting to process parts and build binaries...')
        start = time.clock()


        end = time.clock()

        log.info('Time elapsed: ' + str(end-start))