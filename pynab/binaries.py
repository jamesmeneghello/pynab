import regex
import time
import datetime
import pytz

from pynab.db import db
from pynab import log


CHUNK_SIZE = 500


def merge(a, b, path=None):
    """Merge multi-level dictionaries.
    Kudos: http://stackoverflow.com/questions/7204805/python-dictionaries-of-dictionaries-merge/
    """
    if path is None:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                a[key] = b[key]
                #raise Exception('Conflict at {}: {} {}'.format('.'.join(path + [str(key)]), a[key], b[key]))
        else:
            a[key] = b[key]
    return a


def save(binary):
    """Save a single binary to the DB, including all
    segments/parts (which takes the longest).
    --
    Note: Much quicker. Hooray!
    """
    log.debug('Saving to binary: ' + binary['name'])

    existing_binary = db.binaries.find_one({'name': binary['name']})
    try:
        if existing_binary:
            merge(existing_binary['parts'], binary['parts'])
            db.binaries.update({'_id': existing_binary['_id']}, {
                '$set': {
                    'parts': existing_binary['parts']
                }
            })
        else:
            db.binaries.insert({
                'name': binary['name'],
                'group_name': binary['group_name'],
                'posted': binary['posted'],
                'posted_by': binary['posted_by'],
                'category_id': binary['category_id'],
                'regex_id': binary['regex_id'],
                'req_id': binary['req_id'],
                'xref': binary['xref'],
                'total_parts': binary['total_parts'],
                'parts': binary['parts']
            })
    except:
        log.error('Binary was too large to fit in DB!')


def save_and_clear(binaries=None, parts=None):
    """Helper function to save a set of binaries
    and delete associated parts from the DB. This
    is a lot faster than Newznab's part deletion,
    which routinely took 10+ hours on my server.
    Turns out MySQL kinda sucks at deleting lots
    of shit. If we need more speed, move the parts
    away and drop the temporary table instead."""
    log.info('Saving discovered binaries...')
    for binary in binaries.values():
        save(binary)

    if parts:
        log.info('Removing parts that were either packaged or terrible...')
        db.parts.remove({'_id': {'$in': parts}})


def process():
    """Helper function to process parts into binaries
    based on regex in DB. Copies parts/segments across
    to the binary document. Keeps a list of parts that
    were processed for deletion."""
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
    for part in db.parts.find({'group_name': {'$in': relevant_groups}}, exhaust=True):
        for reg in db.regexes.find({'group_name': {'$in': [part['group_name'], '*']}}).sort('ordinal', 1):
            # convert php-style regex to python
            # ie. /(\w+)/i -> (\w+), regex.I
            # no need to handle s, as it doesn't exist in python

            # why not store it as python to begin with? some regex
            # shouldn't be case-insensitive, and this notation allows for that
            r = reg['regex']
            flags = r[r.rfind('/') + 1:]
            r = r[r.find('/') + 1:r.rfind('/')]
            regex_flags = regex.I if 'i' in flags else 0

            try:
                result = regex.search(r, part['subject'], regex_flags)
            except:
                log.error('Broken regex detected. _id: {:d}, removing...'.format(reg['_id']))
                db.regexes.remove({'_id': reg['_id']})
                continue

            match = result.groupdict() if result else None
            if match:
                log.debug('Matched part {} to {}.'.format(part['subject'], reg['regex']))

                # remove whitespace in dict values
                try:
                    match = {k: v.strip() for k, v in match.items()}
                except:
                    pass

                # fill name if reqid is available
                if match.get('reqid') and not match.get('name'):
                    match['name'] = match['reqid']

                # make sure the regex returns at least some name
                if not match.get('name'):
                    continue

                # if the binary has no part count and is 3 hours old
                # turn it into something anyway
                timediff = pytz.utc.localize(datetime.datetime.now()) \
                           - pytz.utc.localize(part['posted'])

                # if regex are shitty, look for parts manually
                # segment numbers have been stripped by this point, so don't worry
                # about accidentally hitting those instead
                if not match.get('parts'):
                    result = regex.search('(\d{1,3}\/\d{1,3})', part['subject'])
                    if result:
                        match['parts'] = result.group(1)

                # probably an nzb
                if not match.get('parts') and timediff.seconds / 60 / 60 > 3:
                    orphan_binaries.append(match['name'])
                    match['parts'] = '00/00'

                if match.get('name') and match.get('parts'):
                    if match['parts'].find('/') == -1:
                        match['parts'] = match['parts'].replace('-', '/') \
                            .replace('~', '/').replace(' of ', '/') \
                            .replace('[', '').replace(']', '') \
                            .replace('(', '').replace(')', '')

                    current, total = match['parts'].split('/')

                    # if the binary is already in our chunk,
                    # just append to it to reduce query numbers
                    if match['name'] in binaries:
                        binaries[match['name']]['parts'][current] = part
                    else:
                        b = {
                            'name': match['name'],
                            'posted': part['posted'],
                            'posted_by': part['posted_by'],
                            'group_name': part['group_name'],
                            'xref': part['xref'],
                            'regex_id': reg['_id'],
                            'category_id': reg['category_id'],
                            'req_id': match.get('reqid'),
                            'total_parts': int(total),
                            'parts': {current: part}
                        }

                        binaries[match['name']] = b
                    break

        # add the part to a list so we can delete it later
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


def parse_xref(xref):
    """Parse the header XREF into groups."""
    groups = []
    raw_groups = xref.split(' ')
    for raw_group in raw_groups:
        result = regex.search('^([a-z0-9\.\-_]+):(\d+)?$', raw_group, regex.I)
        if result:
            groups.append(result.group(1))
    return groups
