import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.releases
from pynab.db import db_session, Release
from pynab import log


def rename_bad_releases(category):
    count = 0
    s_count = 0
    with db_session() as db:
        query = db.query(Release).filter(Release.category_id==int(category)).filter((Release.files.any())|(Release.nfo!=None)).filter(Release.status!=1)
        for release in query.all():
            count += 1
            name, category_id = pynab.releases.discover_name(release)

            if not name and category_id:
                # don't change the name, but the category might need changing
                release.category_id = category_id

                # we're done with this release
                release.status = 1

                db.add(release)
            elif name and category_id:
                # we found a new name!
                s_count += 1

                release.search_name = pynab.releases.clean_release_name(name)
                release.category_id = category_id

                # we're done with this release
                release.status = 1

                db.add(release)
            else:
                # bad release!
                release.status = 0
                release.unwanted = True
                db.add(release)
        db.commit()

    log.info('rename: successfully renamed {} of {} releases'.format(s_count, count))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='''
    Rename Bad Releases

    Takes either a regex_id or category_id and renames releases from their NFO or filenames.
    Note that you really need to finish post-processing before you can do this.
    ''')
    # not supported yet
    #parser.add_argument('--regex', nargs='?', help='Regex ID of releases to rename')
    parser.add_argument('category', help='Category to rename')

    args = parser.parse_args()

    print('Note: Don\'t run this on a category like TV, only Misc-Other and Books.')
    input('To continue, press enter. To exit, press ctrl-c.')

    if args.category:
        rename_bad_releases(args.category)