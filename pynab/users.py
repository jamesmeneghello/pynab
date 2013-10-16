import hashlib
import uuid

from pynab.db import db
from pynab import log


def create(email):
    """Creates a user by email with a random API key."""
    log.info('Creating user {}...'.format(email))

    api_key = hashlib.md5(uuid.uuid4().bytes)

    user = {
        'email': email,
        'api_key': api_key,
        'grabs': 0
    }

    db.update({'email': email}, user, upsert=True)

    return api_key