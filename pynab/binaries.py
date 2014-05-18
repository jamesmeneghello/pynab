import regex
import time
import datetime
import pytz

from sqlalchemy import *

from pynab.db import db_session, engine, Binary, Part, Regex
from pynab import log


CHUNK_SIZE = 20000


def save(binaries):
    """Helper function to save a set of binaries
    and delete associated parts from the DB. This
    is a lot faster than Newznab's part deletion,
    which routinely took 10+ hours on my server.
    Turns out MySQL kinda sucks at deleting lots
    of shit. If we need more speed, move the parts
    away and drop the temporary table instead."""

    if binaries:
        with db_session() as db:
            existing_binaries = dict(
                ((binary.name, binary) for binary in
                    db.query(Binary.id, Binary.name).filter(Binary.name.in_(binaries.keys())).all()
                )
            )

            binary_inserts = []
            for name, binary in binaries.items():
                existing_binary = existing_binaries.get(name, None)
                if not existing_binary:
                    binary_inserts.append(binary)

            if binary_inserts:
                # this could be optimised slightly with COPY but it's not really worth it
                # there's usually only a hundred or so rows
                engine.execute(Binary.__table__.insert(), binary_inserts)

            existing_binaries = dict(
                ((binary.name, binary) for binary in
                    db.query(Binary.id, Binary.name).filter(Binary.name.in_(binaries.keys())).all()
                )
            )

            update_parts = []
            for name, binary in binaries.items():
                existing_binary = existing_binaries.get(name, None)
                if existing_binary:
                    for number, part in binary['parts'].items():
                        update_parts.append({'_id': part.id, '_binary_id': existing_binary.id})
                else:
                    log.error('something went horribly wrong')

            if update_parts:
                p = Part.__table__.update().where(Part.id==bindparam('_id')).values(binary_id=bindparam('_binary_id'))
                engine.execute(p, update_parts)


def process():
    """Helper function to process parts into binaries
    based on regex in DB. Copies parts/segments across
    to the binary document. Keeps a list of parts that
    were processed for deletion."""

    start = time.time()

    binaries = {}
    orphan_binaries = []
    dead_parts = []
    total_processed = 0
    total_binaries = 0
    count = 0

    # new optimisation: if we only have parts from a couple of groups,
    # we don't want to process the regex for every single one.
    # this removes support for "alt.binaries.games.*", but those weren't
    # used anyway, aside from just * (which it does work with)

    with db_session() as db:
        relevant_groups = db.query(Part.group_name).group_by(Part.group_name).all()
        if relevant_groups:
            # grab all relevant regex
            all_regex = db.query(Regex).filter(Regex.group_name.in_(relevant_groups + ['.*'])).order_by(Regex.ordinal).all()

            # cache compiled regex
            compiled_regex = {}
            for reg in all_regex:
                r = reg.regex
                flags = r[r.rfind('/') + 1:]
                r = r[r.find('/') + 1:r.rfind('/')]
                regex_flags = regex.I if 'i' in flags else 0
                compiled_regex[reg.id] = regex.compile(r, regex_flags)

            query = db.query(Part).filter(Part.group_name.in_(relevant_groups)).filter(Part.binary_id==None)
            total_parts = query.count()
            for part in query.all():
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
                        db.query(Regex).filter(reg.id).remove()
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
                            match['name'] = match['reqid']

                        # make sure the regex returns at least some name
                        if not match.get('name'):
                            continue

                        # if the binary has no part count and is 3 hours old
                        # turn it into something anyway
                        timediff = pytz.utc.localize(datetime.datetime.now()) \
                                   - pytz.utc.localize(part.posted)

                        # if regex are shitty, look for parts manually
                        # segment numbers have been stripped by this point, so don't worry
                        # about accidentally hitting those instead
                        if not match.get('parts'):
                            result = regex.search('(\d{1,3}\/\d{1,3})', part.subject)
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

                            match['parts'] = match['parts'].replace('[', '').replace(']', '') \
                                .replace('(', '').replace(')', '')

                            current, total = match['parts'].split('/')

                            # if the binary is already in our chunk,
                            # just append to it to reduce query numbers
                            if match['name'] in binaries:
                                binaries[match['name']]['parts'][current] = part
                            else:
                                log.debug('binaries: new binary found: {}'.format(match['name']))

                                b = {
                                    'name': match['name'],
                                    'posted': part.posted,
                                    'posted_by': part.posted_by,
                                    'group_name': part.group_name,
                                    'xref': part.xref,
                                    'regex_id': reg.id,
                                    'total_parts': int(total),
                                    'parts': {current: part}
                                }

                                binaries[match['name']] = b
                            found = True
                            break

                # the part matched no regex, so delete it
                if not found:
                    dead_parts.append(part.id)

                if count >= CHUNK_SIZE:
                    total_parts -= count
                    total_binaries += len(binaries)

                    save(binaries)
                    deleted = db.query(Part).filter(Part.id.in_(dead_parts)).delete(synchronize_session=False)

                    log.debug('binary: saved {} binaries and deleted {} dead parts ({} parts left)...'.format(len(binaries), deleted, total_parts))

                    binaries = {}
                    count = 0

            total_binaries += len(binaries)
            save(binaries)
            db.query(Part).filter(Part.id.in_(dead_parts)).delete(synchronize_session=False)

    end = time.time()

    log.info('binary: processed {} parts and formed {} binaries in {:.2f}s'
        .format(total_processed, total_binaries, end - start)
    )


def parse_xref(xref):
    """Parse the header XREF into groups."""
    groups = []
    raw_groups = xref.split(' ')
    for raw_group in raw_groups:
        result = regex.search('^([a-z0-9\.\-_]+):(\d+)?$', raw_group, regex.I)
        if result:
            groups.append(result.group(1))
    return groups
