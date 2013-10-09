import re

import pymongo.errors

from pynab.db import db
from pynab import log


def save(part):
    """Save a single part and segment set to the DB.
    Probably really slow. Some Mongo updates would help
    a lot with this."""
    # because for some reason we can't do a batch find_and_modify
    # upsert into nested embedded dicts
    # i'm probably doing it wrong
    try:
        db.parts.update(
            {
                'subject': part['subject']
            },
            {
                '$set': {
                    'subject': part['subject'],
                    'group_name': part['group_name'],
                    'posted': part['posted'],
                    'posted_by': part['posted_by'],
                    'xref': part['xref'],
                    'total_segments': part['total_segments']
                },
            },
            upsert=True
        )

        # this is going to be slow, probably. unavoidable.
        for skey, segment in part['segments'].items():
            db.parts.update(
                {
                    'subject': part['subject']
                },
                {
                    '$set': {
                        'segments.' + skey: segment
                    }
                }
            )
    except pymongo.errors.PyMongoError as e:
        raise e


def save_all(parts):
    """Save a set of parts to the DB, in a batch if possible."""
    log.info('Saving collected segments and parts...')

    # if possible, do a quick batch insert
    # rarely possible!
    # TODO: filter this more - batch import if first set in group?
    try:
        if db.parts.count() == 0:
            db.parts.insert([value for key, value in parts.items()])
            return True
        else:
            # otherwise, it's going to be slow
            for key, part in parts.items():
                save(part)
            return True
    except pymongo.errors.PyMongoError as e:
        log.error('Could not write parts to db: {0}'.format(e))
        return False


def is_blacklisted(subject, group_name):
    log.debug('{0}: Checking {1} against active blacklists...'.format(group_name, subject))
    blacklists = db.blacklists.find({'status': 1})
    for blacklist in blacklists:
        if re.search(blacklist['group_name'], group_name):
            log.debug('{0}: Checking blacklist {1}...'.format(group_name, blacklist['regex']))
            if re.search(blacklist['regex'], subject):
                return True
    return False