"""
This script will categorise un-categorised releases.

These can pop up from time to time - sometimes from NZB imports with no specified category.

If you get an error about releases without groups, try this in mongo:
# db.releases.find({group:null}).count()
There shouldn't be too many - if not, remove them.
"""
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db
from pynab import log

import pynab.categories


def fix_uncategorised():
    releases = db.releases.find({'$or': [{'category._id': {'$exists': False}}, {'category': None}]})
    total = releases.count()

    found = 0
    for release in releases:
        log.info('Scanning release: {}'.format(release['search_name']))

        if 'group' not in release:
            log.error('Release had no group! Think about deleting releases without groups.')
            continue

        category_id = pynab.categories.determine_category(release['name'], release['group']['name'])
        if category_id:
            category = db.categories.find_one({'_id': category_id})
            # if this isn't a parent category, add those details as well
            if 'parent_id' in category:
                category['parent'] = db.categories.find_one({'_id': category['parent_id']})

            db.releases.update({'_id': release['_id']}, {'$set': {'category': category}})
            found += 1

    log.info('Categorised {:d}/{:d} uncategorised releases.'.format(found, total))


if __name__ == '__main__':
    fix_uncategorised()