"""fix nzbs broken in commit 8b9bce0

Revision ID: 27124764226
Revises: 4efd6f9680d
Create Date: 2014-11-13 16:22:33.207358

"""

# revision identifiers, used by Alembic.
revision = '27124764226'
down_revision = '4efd6f9680d'

from alembic import op
import sqlalchemy as sa

from pynab.db import Release, db_session
from pynab.nzbs import escape
import dateutil.parser
import gzip


def upgrade():
        with db_session() as db:
            for release in db.query(Release). \
                    filter(Release.added >= dateutil.parser.parse('2014/11/12 16:37 GMT+8')). \
                    filter(Release.added <= dateutil.parser.parse('2014/11/13 16:20 GMT+8')). \
                    all():
                nzb = gzip.decompress(release.nzb.data).decode('utf-8')
                if '<?xml' not in nzb:
                    nzb = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                        '<!DOCTYPE nzb PUBLIC "-//newzBin//DTD NZB 1.1//EN" "http://www.newzbin.com/DTD/nzb/nzb-1.1.dtd">\n'
                        '<nzb>\n'
                        '<head><meta type="category">{}</meta><meta type="name">{}</meta></head>\n'.format(release.category.name, escape(release.search_name))) + \
                        nzb
                    release.nzb.data = gzip.compress(nzb.encode('utf-8'))
                    db.commit()


def downgrade():
    pass
