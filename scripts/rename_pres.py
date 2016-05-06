import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.releases
from pynab.db import db_session, Pre, Release
from pynab import log

import config


def rename_pre_releases():
    count = 0

    with db_session() as db:
        query = db.query(Release).filter(Release.pre_id!=None)
        query = query.outerjoin(Pre, Pre.id==Release.pre_id).filter((Release.name!=Pre.name) | (Release.search_name!=Pre.searchname))

        for release in query.all():
            old_category_id = release.category_id

            release.name = release.pre.name
            release.search_name = release.pre.searchname
            release.category_id = pynab.categories.determine_category(release.search_name, release.group.name)

            db.merge(release);

            count += 1
            log.info('rename: [{}] -> [{}]'.format(release.search_name, release.pre.searchname))

    db.commit()

    log.info('rename: successfully renamed {} releases'.format(count))

if __name__ == '__main__':
    print('''
    Rename Releases with mismatched pre-IDs.

    Compares release names with pre-ID names and updates upon mismatch.
    ''')
    input('To continue, press enter. To exit, press ctrl-c.')

    rename_pre_releases()
