import sys
import os

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from sqlalchemy.orm import *
import pynab.nzbs
from pynab.db import db_session, Release
from pynab import log


def fill_sizes():
    with db_session() as db:
        for release in db.query(Release).filter((Release.size==0)|(Release.size==None)).yield_per(500):
            size = pynab.nzbs.get_size(release.nzb)

            if size != 0:
                log.debug('fill_size: [{}] - [{}] - added size: {}'.format(
                    release.id,
                    release.search_name,
                    size
                ))

                release.size = size
                db.add(release)
                db.commit()



if __name__ == '__main__':
    print('This script will fill missing release sizes from NZB information.')
    print('Depending on how many releases are missing sizes, this could take a while.')
    print()
    input('To continue, press enter. To exit, press ctrl-c.')
    fill_sizes()