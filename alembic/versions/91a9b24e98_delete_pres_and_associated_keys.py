"""delete pres and associated keys

Revision ID: 91a9b24e98
Revises: 3821d174074
Create Date: 2015-01-19 08:19:59.461549

"""

# revision identifiers, used by Alembic.
revision = '91a9b24e98'
down_revision = '3821d174074'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_table('pres')
    op.drop_index('ix_releases_pre_id', 'releases')


def downgrade():
    pass
