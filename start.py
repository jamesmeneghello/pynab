import multiprocessing

from pynab import log
from pynab.db import db
import pynab.groups
import pynab.binaries
import pynab.releases
import config


def update(group_name):
    return pynab.groups.update(group_name)


if __name__ == '__main__':
    log.info('Starting update...')

    active_groups = [group['name'] for group in db.groups.find({'active': 1})]
    print(active_groups)
    # maybe: https://bitbucket.org/denis/gevent/src/47aaff4a4324/examples/concurrent_download.py
    # begin with a threaded part update

    with multiprocessing.Pool(processes=config.site['update_threads']) as pool:
        result = pool.map(update, active_groups)


        # process binaries
        # TODO: benchmark threading for this - i suspect it won't do much (mongo table lock)
        #pynab.binaries.process()

        # process releases
        # TODO: likewise
        #pynab.releases.process()
