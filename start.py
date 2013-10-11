import multiprocessing
import time
import logging

from pynab import log
from pynab.db import db

import pynab.groups
import pynab.binaries
import pynab.releases
import pynab.tvrage
import config


def update(group_name):
    return pynab.groups.update(group_name)


if __name__ == '__main__':
    log.info('Starting update...')

    # print MP log as well
    multiprocessing.log_to_stderr().setLevel(logging.DEBUG)

    while True:
        active_groups = [group['name'] for group in db.groups.find({'active': 1})]

        # if maxtasksperchild is more than 1, everything breaks
        # they're long processes usually, so no problem having one task per child
        with multiprocessing.Pool(processes=config.site['update_threads'], maxtasksperchild=1) as pool:
            result = pool.map(update, active_groups)

        # process binaries
        # TODO: benchmark threading for this - i suspect it won't do much (mongo table lock)
        pynab.binaries.process()

        # process releases
        # TODO: likewise
        pynab.releases.process()

        # post-processing

        # grab and append tvrage data to tv releases
        # only do 100 at a time though, so we don't smash the tvrage api
        # when your tvrage table has built up you'll rely on the api less
        pynab.tvrage.process(100)

        # wait for the configured amount of time between cycles
        log.info('Sleeping for {:d} seconds...'.format(config.site['update_wait']))
        time.sleep(config.site['update_wait'])