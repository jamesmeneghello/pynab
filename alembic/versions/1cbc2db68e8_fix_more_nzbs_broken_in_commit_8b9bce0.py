"""fix more nzbs broken in commit 8b9bce0

Revision ID: 1cbc2db68e8
Revises: 27124764226
Create Date: 2014-11-14 12:25:48.872723

"""

# revision identifiers, used by Alembic.
revision = '1cbc2db68e8'
down_revision = '27124764226'

from alembic import op
import sqlalchemy as sa
import sqlalchemy.orm

from pynab.db import Release, db_session
from pynab.nzbs import escape
import dateutil.parser
import gzip


def upgrade():
        with db_session() as db:
            for release in db.query(Release). \
                    filter(Release.added >= dateutil.parser.parse('2014/11/11 00:00 GMT+8')). \
                    filter(Release.added <= dateutil.parser.parse('2014/11/15 00:00 GMT+8')). \
                    order_by(Release.added). \
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
