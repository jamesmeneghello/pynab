import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.ids
from pynab.db import db_session, MetaBlack


def local_postprocess():
    with db_session() as db:
        # noinspection PyComparisonWithNone,PyComparisonWithNone
        db.query(MetaBlack).filter(MetaBlack.status=='IMPOSSIBLE').filter((MetaBlack.movie!=None)|(MetaBlack.tvshow!=None)).delete(synchronize_session=False)

    pynab.ids.process('movie', online=False)
    pynab.ids.process('tv', online=False)


if __name__ == '__main__':
    print('This script will attempt to post-process releases against local databases.')
    print('After importing or collecting a large batch of releases, you can run this once prior to start.py.')
    print('This will check all local matches first, leaving start.py to just do remote matching.')
    print('It\'ll really just save some time.')
    print()
    input('To continue, press enter. To exit, press ctrl-c.')
    local_postprocess()