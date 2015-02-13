import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.releases
from pynab.db import db_session, Release, windowed_query
from pynab import log

import config


def rename_bad_releases(category):
    count = 0
    s_count = 0
    for_deletion = []
    with db_session() as db:
        query = db.query(Release).filter(Release.category_id==int(category)).filter(
            (Release.files.any())|(Release.nfo_id!=None)|(Release.sfv_id!=None)|(Release.pre_id!=None)
        ).filter((Release.status!=1)|(Release.status==None))
        for release in windowed_query(query, Release.id, config.scan.get('binary_process_chunk_size', 1000)):
            count += 1
            name, category_id = pynab.releases.discover_name(release)

            if not name and category_id:
                # don't change the name, but the category might need changing
                release.category_id = category_id

                # we're done with this release
                release.status = 1

                db.merge(release)
            elif name and category_id:
                # only add it if it doesn't exist already
                existing = db.query(Release).filter(Release.name==name,
                                                    Release.group_id==release.group_id,
                                                    Release.posted==release.posted).first()
                if existing:
                    # if it does, delete this one
                    for_deletion.append(release.id)
                    db.expunge(release)
                else:
                    # we found a new name!
                    s_count += 1

                    release.name = name
                    release.search_name = pynab.releases.clean_release_name(name)
                    release.category_id = category_id

                    # we're done with this release
                    release.status = 1

                    db.merge(release)
            else:
                # bad release!
                release.status = 0
                release.unwanted = True
                db.merge(release)
        db.commit()

    if for_deletion:
        deleted = db.query(Release).filter(Release.id.in_(for_deletion)).delete(synchronize_session=False)
    else:
        deleted = 0

    log.info('rename: successfully renamed {} of {} releases and deleted {} duplicates'.format(s_count, count, deleted))


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