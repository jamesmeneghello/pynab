import datetime
import time
import hashlib
import uuid
import re

import pytz
from bson.code import Code

from pynab import log
from pynab.db import db
import config
import pynab.nzbs
import pynab.categories


def clean_release_name(name):
    """Strip dirty characters out of release names. The API
    will match against clean names."""
    chars = ['#', '@', '$', '%', '^', '§', '¨', '©', 'Ö']
    for c in chars:
        name = name.replace(c, '')
    return name.replace('_', ' ')


def process():
    """Helper function to begin processing binaries. Checks
    for 100% completion and will create NZBs/releases for
    each complete release. Will also categorise releases,
    and delete old binaries."""
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

    # returns a list of _ids, so we need to get each binary
    for result in db.binaries.inline_map_reduce(mapper, reducer):
        if result['value']:
            binary = db.binaries.find_one({'_id': result['_id']})

            # check to make sure we have over the configured minimum files
            nfos = []
            rars = []
            pars = []
            rar_count = 0
            par_count = 0
            zip_count = 0

            for number, part in binary['parts'].items():
                if re.search(pynab.nzbs.rar_part_regex, part['subject'], re.I):
                    rar_count += 1
                if re.search(pynab.nzbs.nfo_regex, part['subject'], re.I) and not re.search(pynab.nzbs.metadata_regex,
                                                                                            part['subject'], re.I):
                    nfos.append(part)
                if re.search(pynab.nzbs.rar_regex, part['subject'], re.I) and not re.search(pynab.nzbs.metadata_regex,
                                                                                            part['subject'], re.I):
                    rars.append(part)
                if re.search(pynab.nzbs.par2_regex, part['subject'], re.I):
                    par_count += 1
                    if not re.search(pynab.nzbs.par_vol_regex, part['subject'], re.I):
                        pars.append(part)
                if re.search(pynab.nzbs.zip_regex, part['subject'], re.I) and not re.search(pynab.nzbs.metadata_regex,
                                                                                            part['subject'], re.I):
                    zip_count += 1

            log.debug('Binary {} has {} rars and {} rar_parts.'.format(binary['name'], len(rars), rar_count))

            if rar_count + zip_count < config.site['min_archives']:
                log.debug('Binary does not have the minimum required archives.')
                db.binaries.remove({'_id': binary['_id']})
                continue

            # generate a gid, not useful since we're storing in GridFS
            gid = hashlib.md5(uuid.uuid1().bytes).hexdigest()

            # clean the name for searches
            clean_name = clean_release_name(binary['name'])

            # if the regex used to generate the binary gave a category, use that
            category = None
            if binary['category_id']:
                category = db.categories.find_one({'_id': binary['category_id']})

            # otherwise, categorise it with our giant regex blob
            if not category:
                id = pynab.categories.determine_category(binary['name'], binary['group_name'])
                category = db.categories.find_one({'_id': id})

            # if this isn't a parent category, add those details as well
            if 'parent_id' in category:
                category['parent'] = db.categories.find_one({'_id': category['parent_id']})

            # create the nzb, store it in GridFS and link it here
            nzb, nzb_size = pynab.nzbs.create(gid, clean_name, binary)
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
                            'group': db.groups.find_one({'name': binary['group_name']}, {'name': 1}),
                            'category': category,
                            'nzb': nzb,
                            'nzb_size': nzb_size
                        }
                    },
                    upsert=True
                )

                # delete processed binaries
                db.binaries.remove({'_id': binary['_id']})

    end = time.clock()
    log.info('Time elapsed: {:.2f}s'.format(end - start))
