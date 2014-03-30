import hashlib
import uuid

from pynab.db import db_session, User
from pynab import log


def create(email):
    """Creates a user by email with a random API key."""
    log.info('Creating user {}...'.format(email))

    api_key = hashlib.md5(uuid.uuid4().bytes).hexdigest()

    with db_session() as db:
        user = User()
        user.email = email
        user.api_key = api_key
        user.grabs = 0

        db.merge(user)

    return api_key