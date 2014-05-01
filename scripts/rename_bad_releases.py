import argparse
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.releases
from pynab.db import db
from pynab import log


def rename_bad_releases(category):
    count = 0
    s_count = 0
    for release in db.releases.find({'category._id': int(category), 'unwanted': {'$ne': True}, '$or': [{'nfo': {'$nin': [None, False]}}, {'files.count': {'$exists': True}}]}):
        count += 1
        name, category_id = pynab.releases.discover_name(release)

        if name and not category_id:
            # don't change anything, it was fine
            pass
        elif name and category_id:
            # we found a new name!
            s_count += 1

            category = db.categories.find_one({'_id': category_id})
            category['parent'] = db.categories.find_one({'_id': category['parent_id']})

            db.releases.update({'_id': release['_id']},
                {
                    '$set': {
                        'search_name': pynab.releases.clean_release_name(name),
                        'category': category,
                    }
                }
            )

        else:
            # bad release!
            log.info('Noting unwanted release {} ({:d})...'.format(
                release['search_name'], release['category']['_id'],
            ))

            db.releases.update({'_id': release['_id']},
                {
                    '$set': {
                        'unwanted': True
                    }
                }
            )

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