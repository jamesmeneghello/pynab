"""add set null on regex deletion for binaries

Revision ID: 30688404cda
Revises: 57d67e16149
Create Date: 2015-11-01 21:40:05.083075

"""

# revision identifiers, used by Alembic.
revision = '30688404cda'
down_revision = '57d67e16149'

from alembic import op


def upgrade():
    op.drop_constraint(op.f('binaries_regex_id_fkey'), 'binaries', type_='foreignkey')
    op.create_foreign_key(op.f('binaries_regex_id_fkey'), 'binaries', 'regexes', ['regex_id'], ['id'], ondelete='SET NULL')


def downgrade():
    op.drop_constraint(op.f('binaries_regex_id_fkey'), 'binaries', type_='foreignkey')
    op.create_foreign_key(op.f('binaries_regex_id_fkey'), 'binaries', 'regexes', ['regex_id'], ['id'])
