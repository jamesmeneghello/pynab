import hashlib
import uuid

from pynab.db import db_session, User

def list():
    """List all users."""
    with db_session() as db:
        users = db.query(User).order_by(User.email)
        user_list = []
        for user in users:
            user_list.append([user.email, user.api_key, user.grabs])

        return user_list

def info(email):
    """Information about a specific email."""
    with db_session() as db:
        user = db.query(User).filter(User.email == email).first()
        if user:
            return [user.email, user.api_key, user.grabs]
        else:
            return None

def create(email):
    """Creates a user by email with a random API key."""
    api_key = hashlib.md5(uuid.uuid4().bytes).hexdigest()

    with db_session() as db:
        user = User()
        user.email = email
        user.api_key = api_key
        user.grabs = 0

        db.merge(user)

    return api_key

def delete(email):
    """Deletes a user by email."""

    with db_session() as db:
        deleted = db.query(User).filter(User.email == email).delete()
        if deleted:
            db.commit()
            return True

    return False
