import os
import sys

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

from pynab.db import db
import pynab.nzbs
import config


def process_minarchives():
    """Delete releases that don't conform to min_archives directive."""
    for release in db.releases.find():
        data = pynab.nzbs.get_nzb_dict(release['nzb'])

        if data['rar_count'] + data['zip_count'] < config.site['min_archives']:
            print('DELETING: Release {} has {} rars and {} zips.'.format(release['search_name'], data['rar_count'],
                                                                         data['zip_count']))
            db.releases.remove({'_id': release['_id']})


if __name__ == '__main__':
    print('Process and enforce min_files script.')
    print('Please note that this script is destructive and will delete releases.')
    print('This will clear releases that do not fit the min_archives dictated in config.py.')
    print('This action is permanent and cannot be undone.')
    input('To continue, press enter. To exit, press ctrl-c.')

    process_minarchives()