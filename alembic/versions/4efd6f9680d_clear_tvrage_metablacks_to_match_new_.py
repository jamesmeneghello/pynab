"""clear tvrage metablacks to match new regex

Revision ID: 4efd6f9680d
Revises: 49dd0ca86e1
Create Date: 2014-11-13 00:05:25.572547

"""

# revision identifiers, used by Alembic.
revision = '4efd6f9680d'
down_revision = '49dd0ca86e1'

from pynab.db import db_session, Release, MetaBlack


def upgrade():
    with db_session() as db:
        db.query(Release).\
            filter(Release.tvshow_metablack_id == MetaBlack.id).\
            filter(MetaBlack.status=='IMPOSSIBLE').\
            update({Release.tvshow_metablack_id: None}, synchronize_session='fetch')
        db.commit()


def downgrade():
    pass
