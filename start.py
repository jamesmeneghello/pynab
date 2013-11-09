import multiprocessing
from multiprocessing.pool import Pool
import time
import logging
import signal
import traceback

from pynab import log
from pynab.db import db

import pynab.groups
import pynab.binaries
import pynab.releases
import pynab.tvrage
import pynab.rars
import pynab.nfos
import pynab.imdb
import config


class LogExceptions(object):
    def __init__(self, callable):
        self.__callable = callable
        return

    def __call__(self, *args, **kwargs):
        try:
            result = self.__callable(*args, **kwargs)

        except Exception as e:
            # Here we add some debugging help. If multiprocessing's
            # debugging is on, it will arrange to log the traceback
            mp_error(traceback.format_exc())
            # Re-raise the original exception so the Pool worker can
            # clean up
            raise

        # It was fine, give a normal answer
        return result
    pass


class LoggingPool(Pool):
    def map_async(self, func, iterable=None, chunksize=0, callback=None, error_callback=None):
        return Pool.apply_async(self, LogExceptions(func), iterable, chunksize, callback, error_callback)


def mp_error(msg, *args):
    return multiprocessing.get_logger().exception(msg, *args)


def update(group_name):
    pynab.groups.update(group_name)


def process_tvrage(limit):
    pynab.tvrage.process(limit)


def process_nfos(limit):
    pynab.nfos.process(limit)


def process_rars(limit):
    pynab.rars.process(limit)


def process_imdb(limit):
    pynab.imdb.process(limit)


if __name__ == '__main__':
    log.info('Starting update...')

    # print MP log as well
    multiprocessing.log_to_stderr().setLevel(logging.DEBUG)

    while True:
        active_groups = [group['name'] for group in db.groups.find({'active': 1})]
        if active_groups:
            # if maxtasksperchild is more than 1, everything breaks
            # they're long processes usually, so no problem having one task per child
            pool = multiprocessing.Pool(processes=config.site['update_threads'], maxtasksperchild=1)
            result = pool.map_async(update, active_groups)
            try:
                result.get()
            except Exception as e:
                mp_error(e)

            pool.terminate()
            pool.join()

            # process binaries
            # TODO: benchmark threading for this - i suspect it won't do much (mongo table lock)
            pynab.binaries.process()

            # process releases
            # TODO: likewise
            pynab.releases.process()

            # wait for the configured amount of time between cycles
            log.info('Sleeping for {:d} seconds...'.format(config.site['update_wait']))
            time.sleep(config.site['update_wait'])
        else:
            log.info('No groups active, cancelling start.py...')
            break