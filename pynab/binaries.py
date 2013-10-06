import re
import time
import datetime

import pytz

from pynab.db import db
from pynab import log


CHUNK_SIZE = 500


def save(binary):
    log.debug('Saving to binary: ' + binary['name'])

    # because for some reason we can't do a batch find_and_modify
    # upsert into nested embedded dicts
    # i'm probably doing it wrong
    db.binaries.update(
        {
            'name': binary['name']
        },
        {
            '$set': {
                'name': binary['name'],
                'group_name': binary['group_name'],
                'posted': binary['posted'],
                'posted_by': binary['posted_by'],
                'category_id': binary['category_id'],
                'regex_id': binary['regex_id'],
                'req_id': binary['req_id'],
                'xref': binary['xref'],
                'total_parts': binary['total_parts']
            }
        },
        upsert=True
    )

    # this is going to be slow, probably. unavoidable.
    for pkey, part in binary['parts'].items():
        for skey, segment in part['segments'].items():
            db.binaries.update(
                {
                    'name': binary['name']
                },
                {
                    '$set': {
                        'parts.' + pkey + '.subject': part['subject'],
                        'parts.' + pkey + '.group_name': part['group_name'],
                        'parts.' + pkey + '.posted': part['posted'],
                        'parts.' + pkey + '.posted_by': part['posted_by'],
                        'parts.' + pkey + '.xref': part['xref'],
                        'parts.' + pkey + '.total_segments': part['total_segments'],
                        'parts.' + pkey + '.segments.' + skey: segment
                    }
                }
            )


def save_and_clear(binaries=None, parts=None):
    log.info('Saving discovered binaries...')
    for binary in binaries.values():
        save(binary)

    if parts:
        log.info('Removing parts that were either packaged or terrible...')
        db.parts.remove({'_id': {'$in': parts}})


def process():
    log.info('Starting to process parts and build binaries...')
    start = time.clock()

    binaries = {}
    orphan_binaries = []
    processed_parts = []
    chunk_count = 1
    approx_chunks = db.parts.count() / CHUNK_SIZE

    # new optimisation: if we only have parts from a couple of groups,
    # we don't want to process the regex for every single one.
    # this removes support for "alt.binaries.games.*", but those weren't
    # used anyway, aside from just * (which it does work with)

    # to re-enable that feature in future, mongo supports reverse-regex through
    # where(), but it's slow as hell because it's processed by the JS engine
    relevant_groups = db.parts.distinct('group_name')
    for regex in db.regexes.find({'group_name': {'$in': relevant_groups + ['*']}}):
        log.debug('Matching to regex: ' + regex['regex'])

        for part in db.parts.find({'group_name': {'$in': relevant_groups}}, exhaust=True):
            # convert php-style regex to python
            # ie. /(\w+)/i -> (\w+), re.I
            # no need to handle s, as it doesn't exist in python

            # why not store it as python to begin with? some regex
            # shouldn't be case-insensitive, and this notation allows for that
            r = regex['regex']
            flags = r[r.rfind('/') + 1:]
            r = r[r.find('/') + 1:r.rfind('/')]
            regex_flags = re.I if 'i' in flags else 0

            result = re.search(r, part['subject'], regex_flags)
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
                           - pytz.utc.localize(part['posted'])

                if not match.get('parts') and timediff.seconds / 60 / 60 > 3:
                    orphan_binaries.append(match['name'])
                    match['parts'] = '01/01'

                if match.get('name') and match.get('parts'):
                    if match['parts'].find('/') == -1:
                        match['parts'] = match['parts'].replace('-', '/') \
                            .replace('~', '/').replace(' of ', '/')

                    repost = re.search('(repost|re\-?up)', match['name'], flags=re.I)
                    if repost:
                        match['name'] += ' ' + result.group(0)

                    current, total = match['parts'].split('/')

                    if match['name'] in binaries:
                        binaries[match['name']]['parts'][current] = part
                    else:
                        b = {
                            'name': match['name'],
                            'posted': part['posted'],
                            'posted_by': part['posted_by'],
                            'group_name': part['group_name'],
                            'xref': part['xref'],
                            'regex_id': regex['_id'],
                            'category_id': regex['category_id'],
                            'req_id': match.get('reqid'),
                            'total_parts': int(total),
                            'parts': {current: part}
                        }

                        binaries[match['name']] = b

            processed_parts.append(part['_id'])

            # save and delete stuff in chunks
            if len(processed_parts) >= CHUNK_SIZE:
                log.info('Processing chunk {0:d} of approx {1:.1f} with {2:d} parts...'
                .format(chunk_count, approx_chunks, CHUNK_SIZE)
                )
                chunk_count += 1
                save_and_clear(binaries, processed_parts)
                processed_parts = []
                binaries = {}

    # clear off whatever's left
    save_and_clear(binaries, processed_parts)

    end = time.clock()
    log.info('Time elapsed: {:.2f}s'.format(end - start))


