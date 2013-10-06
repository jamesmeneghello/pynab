from pynab.db import db
from pynab import log


def save(part):
    # because for some reason we can't do a batch find_and_modify
    # upsert into nested embedded dicts
    # i'm probably doing it wrong
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


def save_all(parts):
    log.info('Saving collected segments and parts...')
    # if possible, do a quick batch insert
    if db.parts.count() == 0:
        db.parts.insert([value for key, value in parts.items()])
    else:
        # otherwise, it's going to be slow
        for key, part in parts.items():
            save(part)
