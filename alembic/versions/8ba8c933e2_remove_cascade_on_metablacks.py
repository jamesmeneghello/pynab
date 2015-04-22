"""remove cascade on metablacks

Revision ID: 8ba8c933e2
Revises: a06db5300d
Create Date: 2015-04-22 23:35:05.750527

"""

# revision identifiers, used by Alembic.
revision = '8ba8c933e2'
down_revision = 'a06db5300d'

from alembic import op
import sqlalchemy as sa


def upgrade():
    op.drop_constraint('releases_nfo_metablack_id_fkey', 'releases')
    op.create_foreign_key(op.f('releases_nfo_metablack_id_fkey'),
                          'releases', 'metablack', ['nfo_metablack_id'],
                          ['id'],
                          ondelete='SET NULL'
                          )

    op.drop_constraint('releases_movie_metablack_id_fkey', 'releases')
    op.create_foreign_key(op.f('releases_movie_metablack_id_fkey'),
                          'releases', 'metablack', ['movie_metablack_id'],
                          ['id'],
                          ondelete='SET NULL'
                          )

    op.drop_constraint('releases_rar_metablack_id_fkey', 'releases')
    op.create_foreign_key(op.f('releases_rar_metablack_id_fkey'),
                          'releases', 'metablack', ['rar_metablack_id'],
                          ['id'],
                          ondelete='SET NULL'
                          )

    op.drop_constraint('releases_tvshow_metablack_id_fkey', 'releases')
    op.create_foreign_key(op.f('releases_tvshow_metablack_id_fkey'),
                          'releases', 'metablack', ['tvshow_metablack_id'],
                          ['id'],
                          ondelete='SET NULL'
                          )

    op.drop_constraint('releases_sfv_metablack_id_fkey', 'releases')
    op.create_foreign_key(op.f('releases_sfv_metablack_id_fkey'),
                          'releases', 'metablack', ['sfv_metablack_id'],
                          ['id'],
                          ondelete='SET NULL'
                          )


def downgrade():
    pass