import datetime
import time
import hashlib
import uuid
import pytz

from bson.code import Code

from pynab import log
from pynab.db import db

import pynab.nzb
import pynab.categories


def clean_release_name(name):
    chars = ['#', '@', '$', '%', '^', '§', '¨', '©', 'Ö']
    for c in chars:
        name = name.replace(c, '')
    return name.replace('_', ' ')


def process():
    log.info('Processing complete binaries and generating releases...')
    start = time.clock()

    # mapreduce isn't really supposed to be run in real-time
    # then again, processing releases isn't a real-time op
    mapper = Code("""
        function() {
            var complete = true;
            parts_length = Object.keys(this.parts).length;
            if (parts_length >= this.total_parts) {
                for (var key in this.parts) {
                    segments_length = Object.keys(this.parts[key].segments).length;
                    if (segments_length < this.parts[key].total_segments) {
                        complete = false
                    }
                }
            } else {
                complete = false
            }
            emit(this._id, complete)
        }
    """)

    # no reduce needed, since we're returning single values
    reducer = Code("""function(key, values){}""")

    for result in db.binaries.inline_map_reduce(mapper, reducer):
        if result['value']:
            binary = db.binaries.find_one({'_id': result['_id']})
            gid = hashlib.md5(uuid.uuid1().bytes).hexdigest()
            clean_name = clean_release_name(binary['name'])

            category_id = None
            if binary['category_id']:
                result = db.categories.find_one({'id': binary['category_id']})
                if result:
                    category_id = result['_id']

            if not category_id:
                id = pynab.categories.determine_category(binary['name'], binary['group_name'])
                category_id = db.categories.find_one({'id': id})['_id']

            nzb = pynab.nzb.create(gid, clean_name, binary)
            if nzb:
                log.debug('Adding release: {0}'.format(clean_name))

                db.releases.update(
                    {
                        'search_name': binary['name'],
                        'posted': binary['posted']
                    },
                    {
                        '$setOnInsert': {
                            'id': gid,
                            'added': pytz.utc.localize(datetime.datetime.now()),
                            'size': None,
                            'spotnab_id': None,
                            'completion': None,
                            'grabs': 0,
                            'passworded': None,
                            'file_count': None,
                            'tvrage': None,
                            'tvdb': None,
                            'imdb': None,
                            'nfo': None,
                            'tv': None,
                        },
                        '$set': {
                            'name': clean_name,
                            'search_name': clean_name,
                            'total_parts': binary['total_parts'],
                            'posted': binary['posted'],
                            'posted_by': binary['posted_by'],
                            'status': 1,
                            'updated': pytz.utc.localize(datetime.datetime.now()),
                            'group_id': db.groups.find_one({'name': binary['group_name']})['_id'],
                            'category_id': category_id,
                            'nzb': nzb
                        }
                    },
                    upsert=True
                )

                db.binaries.remove({'_id': binary['_id']})

    end = time.clock()
    log.info('Time elapsed: {:.2f}s'.format(end - start))