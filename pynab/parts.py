import regex

import pymongo.errors

from pynab.db import db
from pynab import log


def save(part):
    """Save a single part and segment set to the DB.
    Probably really slow. Some Mongo updates would help
    a lot with this.
    ---
    Note: no longer as slow.
    """
    # because for some reason we can't do a batch find_and_modify
    # upsert into nested embedded dicts
    # i'm probably doing it wrong
    try:
        existing_part = db.parts.find_one({'subject': part['subject']})
        if existing_part:
            existing_part['segments'].update(part['segments'])
            db.parts.update({'_id': existing_part['_id']}, {
                '$set': {
                    'segments': existing_part['segments']
                }
            })
        else:
            db.parts.insert({
                'subject': part['subject'],
                'group_name': part['group_name'],
                'posted': part['posted'],
                'posted_by': part['posted_by'],
                'xref': part['xref'],
                'total_segments': part['total_segments'],
                'segments': part['segments']
            })

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
    #log.debug('{0}: Checking {1} against active blacklists...'.format(group_name, subject))
    blacklists = db.blacklists.find({'status': 1})
    for blacklist in blacklists:
        if regex.search(blacklist['group_name'], group_name):
            # too spammy
            #log.debug('{0}: Checking blacklist {1}...'.format(group_name, blacklist['regex']))
            if regex.search(blacklist['regex'], subject):
                return True
    return False