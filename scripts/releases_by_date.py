import sys
import os
from sqlalchemy import func

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import Release, db_session


def main():
    with db_session() as db:
        for date in db.query(func.DATE(Release.added), func.count(Release.id))\
                .group_by(func.DATE(Release.added))\
                .order_by(func.DATE(Release.added)).all():
            print('{0} {1:10d}'.format(date[0], date[1]))


if __name__ == '__main__':
    main()