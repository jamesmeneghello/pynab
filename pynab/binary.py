import time
import re
import pytz
import datetime
import pymongo.errors as errors
import pprint
from pynab import log
from pynab.db import db, Collection
from pynab.group import Group
from pynab.regex import Regex
from pynab.part import Part

class Binary(Collection):
    _collection = 'binaries'

    def __init__(self, name='', posted='', posted_by='', group_name='', xref='', category_id=None, regex_id=None, req_id='', total_parts=0, parts=list(), _id=None, **kwargs):
        self.id = _id
        self.name = name
        self.posted = posted
        self.posted_by = posted_by
        self.group_name = group_name
        self.xref = xref
        self.category_id = category_id
        self.regex_id = regex_id
        self.req_id = req_id
        self.total_parts = total_parts
        self.parts = parts

    def check_and_merge(self):
        if self.id:
            query = {'id': self.id}
        else:
            query = {
                'name': self.name
            }
        b = Binary.get_one(**query)
        if b:
            #merge parts
            self.parts = list(set(b.parts + self.parts))

    def save(self):
        self.check_and_merge()
        self._save()

    def _save(self):
        try:
            self.id = db[self._collection].find_and_modify(
                query={
                    'name': self.name
                },
                update={
                    '$set': {
                        'name': self.name,
                        'posted': self.posted,
                        'posted_by': self.posted_by,
                        'xref': self.xref,
                        'group_name': self.group_name,
                        'regex_id': self.regex_id,
                        'category_id': self.category_id,
                        'req_id': self.req_id,
                        'total_parts': self.total_parts,
                        'parts': [p.dict() for p in self.parts]
                    }
                },
                new=True,
                upsert=True
            ).get('_id')
            return True
        except errors.OperationFailure as e:
            log.error(e)
            return False

    def size(self):
        total = 0
        for part in self.parts:
            total += part.size()
        return total

    def post_get(self):
        # pycharm got this one wrong
        self.parts = [Part(**p) for p in self.parts]
        [p.post_get() for p in self.parts]

    @classmethod
    def process(cls):
        log.info('Starting to process parts and build binaries...')
        start = time.clock()

        groups = db.groups.distinct('group_name')
        groups += ['*']
        for regex in Regex.get(group_name={'$in': groups}):
            log.debug('Matching to regex: ' + regex.regex)

            if re.search('\*$', regex.group_name):
                search = regex.group_name[:-1]
                if search == '':
                    query = {}
                else:
                    query = {'name': {'$regex': '^' + regex.group_name[:-1]}}
            else:
                query = {'name': regex.group_name}

            binaries = []
            orphan_binaries = []
            groups = [g.name for g in Group.get(**query)]

            for part in Part.get(group_name={'$in': groups}, exhaust=True):
                r = regex.regex
                flags = r[r.rfind('/') + 1:]
                r = r[r.find('/') + 1:r.rfind('/')]
                regex_flags = re.I if 'i' in flags else 0

                result = re.search(r, part.subject, regex_flags)
                match = result.groupdict() if result else None
                if match:
                    # remove whitespace in dict values
                    match = {k: v.strip() for k, v in match.items()}

                    # fill name if reqid is available
                    if match.get('reqid') and not match.get('name'):
                        match['name'] = match['reqid']

                    # make sure the regex returns at least some name
                    if not match.get('name'):
                        continue

                    timediff = pytz.utc.localize(datetime.datetime.now()) \
                           - pytz.utc.localize(part.posted)

                    if not match.get('parts') and timediff.seconds / 60 / 60 > 3:
                        orphan_binaries.append(match['name'])
                        match['parts'] = '01/01'

                    if match.get('name') and match.get('parts'):
                        if match['parts'].find('/') == -1:
                            match['parts'] = match['parts'].replace('-', '/').replace('~', '/').replace(' of ', '/')

                        if re.search('repost|re\-?up', match['name'], flags=re.I):
                            result = re.search('repost\d?|re\-?up', part['subject'], re.I)
                            if result:
                                match['name'] += ' ' + result[0]

                        current, total = match['parts'].split('/')

                        b = Binary(
                            name=match['name'],
                            posted=part.posted,
                            posted_by=part.posted_by,
                            group_name=part.group_name,
                            xref=part.xref,
                            regex_id=regex.id,
                            category_id=regex.category_id,
                            req_id=match.get('reqid'),
                            total_parts=int(total),
                            parts=[part]
                        )

                        b.save()

        end = time.clock()

        log.info('Time elapsed: ' + str(end-start))

