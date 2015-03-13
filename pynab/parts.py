import time
import io
import pyhashxx
import struct

import regex
from sqlalchemy.orm import Load, subqueryload

from pynab.db import db_session, engine, Part, Segment, copy_file
from pynab import log


def generate_hash(subject, posted_by, group_name, total_segments):
    """Generates a mostly-unique temporary hash for a part."""
    return pyhashxx.hashxx(subject.encode('utf-8'), posted_by.encode('utf-8'),
                           group_name.encode('utf-8'), struct.pack('I', total_segments)
    )


def save_all(parts):
    """Save a set of parts to the DB, in a batch if possible."""

    if parts:
        start = time.time()
        group_name = list(parts.values())[0]['group_name']

        with db_session() as db:
            # this is a little tricky. parts have no uniqueness at all.
            # no uniqid and the posted dates can change since it's based off the first
            # segment that we see in that part, which is different for each scan.
            # what we do is get the next-closest thing (subject+author+group) and
            # order it by oldest first, so when it's building the dict the newest parts
            # end on top (which are the most likely to be being saved to).

            # realistically, it shouldn't be a big problem - parts aren't stored in the db
            # for very long anyway, and they're only a problem while there. saving 500 million
            # segments to the db is probably not a great idea anyway.
            existing_parts = dict(
                ((part.hash, part) for part in
                 db.query(Part.id, Part.hash).filter(Part.hash.in_(parts.keys())).filter(
                     Part.group_name == group_name).order_by(Part.posted.asc()).all()
                )
            )

            part_inserts = []
            for hash, part in parts.items():
                existing_part = existing_parts.get(hash, None)
                if not existing_part:
                    segments = part.pop('segments')
                    part_inserts.append(part)
                    part['segments'] = segments

            if part_inserts:
                ordering = ['hash', 'subject', 'group_name', 'posted', 'posted_by', 'total_segments', 'xref']

                s = io.StringIO()
                for part in part_inserts:
                    for item in ordering:
                        if item == 'posted':
                            s.write('"' + part[item].replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S').replace('"',
                                                                                                                '\\"') + '",')
                        elif item == 'xref':
                            # leave off the comma
                            s.write('"' + part[item].replace('"', '\\"') + '"')
                        else:
                            s.write('"' + str(part[item].encode('utf-8', 'replace').decode()).replace('"', '\\"') + '",')
                    s.write("\n")
                s.seek(0)

                if not copy_file(engine, s, ordering, Part):
                    return False

                db.close()

        with db_session() as db:
            existing_parts = dict(
                ((part.hash, part) for part in
                 db.query(Part)
                .options(
                     subqueryload('segments'),
                     Load(Part).load_only(Part.id, Part.hash),
                     Load(Segment).load_only(Segment.id, Segment.segment)
                 )
                .filter(Part.hash.in_(parts.keys()))
                .filter(Part.group_name == group_name)
                .order_by(Part.posted.asc())
                .all()
                )
            )

            segment_inserts = []
            for hash, part in parts.items():
                existing_part = existing_parts.get(hash, None)
                if existing_part:
                    segments = dict(((s.segment, s) for s in existing_part.segments))
                    for segment_number, segment in part['segments'].items():
                        if int(segment_number) not in segments:
                            segment['part_id'] = existing_part.id
                            segment_inserts.append(segment)
                        else:
                            # we hit a duplicate message for a part
                            # kinda wish people would stop reposting shit constantly
                            pass
                else:
                    log.critical(
                        'parts: part didn\'t exist when we went to save it. backfilling with dead_binary_age not set to 0?')
                    return False

            if segment_inserts:
                ordering = ['segment', 'size', 'message_id', 'part_id']

                s = io.StringIO()
                for segment in segment_inserts:
                    for item in ordering:
                        if item == 'part_id':
                            # leave off the tab
                            s.write('"' + str(segment[item]).replace('"', '\\"') + '"')
                        else:
                            s.write('"' + str(segment[item]).replace('"', '\\"') + '",')
                    s.write("\n")
                s.seek(0)

                if not copy_file(engine, s, ordering, Segment):
                    return False

                db.close()

        end = time.time()

        log.debug('parts: saved {} parts and {} segments in {:.2f}s'.format(
            len(part_inserts),
            len(segment_inserts),
            end - start
        ))

    return True


def is_blacklisted(part, group_name, blacklists):
    for blacklist in blacklists:
        if regex.search(blacklist.group_name, group_name):
            # too spammy
            # log.debug('{0}: Checking blacklist {1}...'.format(group_name, blacklist['regex']))
            if regex.search(blacklist.regex, part[blacklist.field]):
                return True
    return False