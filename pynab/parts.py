import regex
import time
import io

from pynab.db import db_session, engine, Part, Segment
from pynab import log

from sqlalchemy.orm import Load, subqueryload


def save_all(parts):
    """Save a set of parts to the DB, in a batch if possible."""

    if parts:
        start = time.time()

        with db_session() as db:
            existing_parts = dict(
                ((part.subject, part) for part in
                    db.query(Part.id, Part.subject).filter(Part.subject.in_(parts.keys())).all()
                )
            )

            part_inserts = []
            for subject, part in parts.items():
                existing_part = existing_parts.get(subject, None)
                if not existing_part:
                    segments = part.pop('segments')
                    part_inserts.append(part)
                    part['segments'] = segments

            if part_inserts:
                ordering = ['subject', 'group_name', 'posted', 'posted_by', 'total_segments', 'xref']

                s = io.StringIO()
                for part in part_inserts:
                    for item in ordering:
                        if item == 'posted':
                            s.write(part[item].replace(tzinfo=None).strftime('%Y-%m-%d %H:%M:%S') + "\t")
                        elif item == 'xref':
                            # leave off the tab
                            s.write(part[item])
                        else:
                            s.write(str(part[item]) + "\t")
                    s.write("\n")
                s.seek(0)

                conn = engine.raw_connection()
                cur = conn.cursor()
                insert_start = time.time()
                cur.copy_from(s, 'parts', columns=ordering)
                conn.commit()
                insert_end = time.time()
                log.debug('Time: {:.2f}s'.format(insert_end - insert_start))

                #engine.execute(Part.__table__.insert(), part_inserts)

            existing_parts = dict(
                ((part.subject, part) for part in
                    db.query(Part)
                    .options(
                        subqueryload('segments'),
                        Load(Part).load_only(Part.id, Part.subject),
                        Load(Segment).load_only(Segment.id, Segment.segment)
                    )
                    .filter(Part.subject.in_(parts.keys()))
                    .all()
                )
            )

            segment_inserts = []
            for subject, part in parts.items():
                existing_part = existing_parts.get(subject, None)
                if existing_part:
                    segments = dict(((s.segment, s) for s in existing_part.segments))
                    for segment_number, segment in part['segments'].items():
                        if int(segment_number) not in segments:
                            segment['part_id'] = existing_part.id
                            segment_inserts.append(segment)
                else:
                    log.error('i\'ve made a huge mistake')

            if segment_inserts:
                ordering = ['segment', 'size', 'message_id', 'part_id']

                s = io.StringIO()
                for segment in segment_inserts:
                    for item in ordering:
                        if item == 'part_id':
                            # leave off the tab
                            s.write(str(segment[item]))
                        else:
                            s.write(str(segment[item]) + "\t")
                    s.write("\n")
                s.seek(0)

                conn = engine.raw_connection()
                cur = conn.cursor()
                insert_start = time.time()
                cur.copy_from(s, 'segments', columns=ordering)
                conn.commit()
                insert_end = time.time()
                log.debug('parts: postgres copy time: {:.2f}s'.format(insert_end - insert_start))

                #engine.execute(Segment.__table__.insert(), segment_inserts)

        end = time.time()

        log.debug('parts: saved {} parts and {} segments in {:.2f}s'.format(
            len(part_inserts),
            len(segment_inserts),
            end - start
        ))


def is_blacklisted(subject, group_name, blacklists):
    for blacklist in blacklists:
        if regex.search(blacklist['group_name'], group_name):
            # too spammy
            #log.debug('{0}: Checking blacklist {1}...'.format(group_name, blacklist['regex']))
            if regex.search(blacklist['regex'], subject):
                return True
    return False