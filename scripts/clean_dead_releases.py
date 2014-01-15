import pymongo
import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import pynab.releases
import pynab.nzbs
from pynab.db import db


def clean_dead_releases():
    i = 0
    for release in db.releases.find({'nzb_size': {'$lt': 1000}}).sort('posted', pymongo.ASCENDING).batch_size(50):
        if not pynab.nzbs.get_nzb_dict(release['nzb']):
            print('Deleting {} ({})...'.format(release['search_name'], release['nzb_size']))
            db.releases.remove({'id': release['id']})

        i += 1
        if i % 50 == 0:
            print('Processed {} releases...'.format(i))

if __name__ == '__main__':
    print('''
    Clean Dead Releases

    This will delete any releases whose NZB contains no files - dead releases.
    ''')
    print('Warning: Obviously, this is destructive.')
    input('To continue, press enter. To exit, press ctrl-c.')

    clean_dead_releases()