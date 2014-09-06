import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db_session, Release, Group
import pynab.categories


def recategorise():
    with db_session() as db:
        i = 0
        for release in db.query(Release).join(Group).all():
            category_id = pynab.categories.determine_category(release.search_name, release.group.name)
            release.category_id = category_id
            db.merge(release)
            i += 1
            # commit every 50k rows
            if i == 50000:
                db.commit()
                i = 0


if __name__ == '__main__':
    print('''
    Recategorise Everything

    Obvious, recategorises everything. Can be useful if you pull in a bad dump.
    Destructive, can do weird things.
    ''')
    input('To continue, press enter. To exit, press ctrl-c.')
    recategorise()