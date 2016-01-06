import time
import pyhashxx

import regex
from sqlalchemy import *

from pynab.db import db_session, Binary, Part, Regex, windowed_query
from pynab import log
import config


PART_REGEX = regex.compile(
    '[\[\( ]((\d{1,3}\/\d{1,3})|(\d{1,3} of \d{1,3})|(\d{1,3}-\d{1,3})|(\d{1,3}~\d{1,3}))[\)\] ]', regex.I)
XREF_REGEX = regex.compile('^([a-z0-9\.\-_]+):(\d+)?$', regex.I)


def generate_hash(name, group_name, posted_by, total_parts):
    """Generates a mostly-unique temporary hash for a part."""
    return pyhashxx.hashxx(name.encode('utf-8'), posted_by.encode('utf-8'),
                           group_name.encode('utf-8'), total_parts.encode('utf-8')
    )


def save(db, binaries):
    """Helper function to save a set of binaries
    and delete associated parts from the DB. This
    is a lot faster than Newznab's part deletion,
    which routinely took 10+ hours on my server.
    Turns out MySQL kinda sucks at deleting lots
    of shit. If we need more speed, move the parts
    away and drop the temporary table instead."""

    if binaries:
        existing_binaries = dict(
            ((binary.hash, binary) for binary in
             db.query(Binary.id, Binary.hash).filter(Binary.hash.in_(binaries.keys())).all()
            )
        )

        binary_inserts = []
        for hash, binary in binaries.items():
            existing_binary = existing_binaries.get(hash, None)
            if not existing_binary:
                binary_inserts.append(binary)

        if binary_inserts:
            # this could be optimised slightly with COPY but it's not really worth it
            # there's usually only a hundred or so rows
            db.execute(Binary.__table__.insert(), binary_inserts)
            db.commit()

        existing_binaries = dict(
            ((binary.hash, binary) for binary in
             db.query(Binary.id, Binary.hash).filter(Binary.hash.in_(binaries.keys())).all()
            )
        )

        update_parts = []
        for hash, binary in binaries.items():
            existing_binary = existing_binaries.get(hash, None)
            if existing_binary:
                for number, part in binary['parts'].items():
                    update_parts.append({'_id': part.id, '_binary_id': existing_binary.id})
            else:
                log.error('something went horribly wrong')

        if update_parts:
            p = Part.__table__.update().where(Part.id == bindparam('_id')).values(binary_id=bindparam('_binary_id'))
            db.execute(p, update_parts)
            db.commit()


def process():
    """Helper function to process parts into binaries
    based on regex in DB. Copies parts/segments across
    to the binary document. Keeps a list of parts that
    were processed for deletion."""

    start = time.time()

    binaries = {}
    dead_parts = []
    total_processed = 0
    total_binaries = 0
    count = 0

    # new optimisation: if we only have parts from a couple of groups,
    # we don't want to process the regex for every single one.
    # this removes support for "alt.binaries.games.*", but those weren't
    # used anyway, aside from just * (which it does work with)

    with db_session() as db:
        db.expire_on_commit = False
        relevant_groups = [x[0] for x in db.query(Part.group_name).group_by(Part.group_name).all()]
        if relevant_groups:
            # grab all relevant regex
            all_regex = db.query(Regex).filter(Regex.status == True).filter(
                Regex.group_name.in_(relevant_groups + ['.*'])).order_by(Regex.ordinal).all()

            # cache compiled regex
            compiled_regex = {}
            for reg in all_regex:
                r = reg.regex
                flags = r[r.rfind('/') + 1:]
                r = r[r.find('/') + 1:r.rfind('/')]
                regex_flags = regex.I if 'i' in flags else 0
                try:
                    compiled_regex[reg.id] = regex.compile(r, regex_flags)
                except Exception as e:
                    log.error('binary: broken regex detected. id: {:d}, removing...'.format(reg.id))
                    db.query(Regex).filter(Regex.id==reg.id).delete()
                    db.commit()

            if not all_regex:
                log.warning('binary: no regexes available for any groups being processed. update your regex?')

            # noinspection PyComparisonWithNone
            query = db.query(Part).filter(Part.group_name.in_(relevant_groups)).filter(Part.binary_id == None)
            total_parts = query.count()
            for part in windowed_query(query, Part.id, config.scan.get('binary_process_chunk_size', 1000)):
                found = False
                total_processed += 1
                count += 1

                for reg in all_regex:
                    if reg.group_name != part.group_name and reg.group_name != '.*':
                        continue

                    # convert php-style regex to python
                    # ie. /(\w+)/i -> (\w+), regex.I
                    # no need to handle s, as it doesn't exist in python

                    # why not store it as python to begin with? some regex
                    # shouldn't be case-insensitive, and this notation allows for that

                    try:
                        result = compiled_regex[reg.id].search(part.subject)
                    except:
                        log.error('binary: broken regex detected. id: {:d}, removing...'.format(reg.id))
                        all_regex.remove(reg)
                        db.query(Regex).filter(Regex.id==reg.id).delete()
                        db.commit()
                        continue

                    match = result.groupdict() if result else None
                    if match:
                        # remove whitespace in dict values
                        try:
                            match = {k: v.strip() for k, v in match.items()}
                        except:
                            pass

                        # fill name if reqid is available
                        if match.get('reqid') and not match.get('name'):
                            match['name'] = '{}'.format(match['reqid'])

                        # make sure the regex returns at least some name
                        if not match.get('name'):
                            match['name'] = ' '.join([v for v in match.values() if v])

                        # if regex are shitty, look for parts manually
                        # segment numbers have been stripped by this point, so don't worry
                        # about accidentally hitting those instead
                        if not match.get('parts'):
                            result = PART_REGEX.search(part.subject)
                            if result:
                                match['parts'] = result.group(1)

                        if match.get('name') and match.get('parts'):
                            if match['parts'].find('/') == -1:
                                match['parts'] = match['parts'].replace('-', '/') \
                                    .replace('~', '/').replace(' of ', '/')

                            match['parts'] = match['parts'].replace('[', '').replace(']', '') \
                                .replace('(', '').replace(')', '')

                            if '/' not in match['parts']:
                                continue

                            current, total = match['parts'].split('/')

                            # calculate binary hash for matching
                            hash = generate_hash(match['name'], part.group_name, part.posted_by, total)

                            # if the binary is already in our chunk,
                            # just append to it to reduce query numbers
                            if hash in binaries:
                                if current in binaries[hash]['parts']:
                                    # but if we already have this part, pick the one closest to the binary
                                    if binaries[hash]['posted'] - part.posted < binaries[hash]['posted'] - \
                                            binaries[hash]['parts'][current].posted:
                                        binaries[hash]['parts'][current] = part
                                    else:
                                        dead_parts.append(part.id)
                                        break
                                else:
                                    binaries[hash]['parts'][current] = part
                            else:
                                log.debug('binaries: new binary found: {}'.format(match['name']))

                                b = {
                                    'hash': hash,
                                    'name': match['name'],
                                    'posted': part.posted,
                                    'posted_by': part.posted_by,
                                    'group_name': part.group_name,
                                    'xref': part.xref,
                                    'regex_id': reg.id,
                                    'total_parts': int(total),
                                    'parts': {current: part}
                                }

                                binaries[hash] = b
                            found = True
                            break

                # the part matched no regex, so delete it
                if not found:
                    dead_parts.append(part.id)

                if count >= config.scan.get('binary_process_chunk_size', 1000) or (total_parts - count) == 0:
                    total_parts -= count
                    total_binaries += len(binaries)

                    save(db, binaries)
                    if dead_parts:
                        deleted = db.query(Part).filter(Part.id.in_(dead_parts)).delete(synchronize_session='fetch')
                    else:
                        deleted = 0

                    db.commit()
                    log.info(
                        'binary: saved {} binaries and deleted {} dead parts ({} parts left)...'.format(len(binaries),
                                                                                                        deleted,
                                                                                                        total_parts))

                    binaries = {}
                    dead_parts = []
                    count = 0

        db.expire_on_commit = True
        db.close()

    end = time.time()

    log.info('binary: processed {} parts and formed {} binaries in {:.2f}s'
             .format(total_processed, total_binaries, end - start)
    )


def parse_xref(xref):
    """Parse the header XREF into groups."""
    groups = []
    raw_groups = xref.split(' ')
    for raw_group in raw_groups:
        result = XREF_REGEX.search(raw_group)
        if result:
            groups.append(result.group(1))
    return groups
