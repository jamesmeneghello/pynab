import multiprocessing
import time
import logging
import signal

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


def init_update():
    signal.signal(signal.SIGINT, signal.SIG_IGN)


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
            pool = multiprocessing.Pool(processes=config.site['update_threads'], initializer=init_update,
                                        maxtasksperchild=1)
            try:
                result = pool.map(update, active_groups)
                pool.terminate()
                pool.join()
            except KeyboardInterrupt:
                log.info('Caught ctrl-c, terminating workers.')
                pool.terminate()
                pool.join()

            # process binaries
            # TODO: benchmark threading for this - i suspect it won't do much (mongo table lock)
            pynab.binaries.process()

            # process releases
            # TODO: likewise
            pynab.releases.process()

            # post-processing

            # grab and append tvrage data to tv releases
            tvrage_p = None
            if config.site['process_tvrage']:
                tvrage_p = multiprocessing.Process(target=process_tvrage, args=(config.site['tvrage_limit'],))
                tvrage_p.start()

            imdb_p = None
            if config.site['process_imdb']:
                imdb_p = multiprocessing.Process(target=process_imdb, args=(config.site['imdb_limit'],))
                imdb_p.start()

            # grab and append nfo data to all releases
            nfo_p = None
            if config.site['process_nfos']:
                nfo_p = multiprocessing.Process(target=process_nfos, args=(config.site['nfo_limit'],))
                nfo_p.start()

            # check for passwords, file count and size
            rar_p = None
            if config.site['process_rars']:
                rar_p = multiprocessing.Process(target=process_rars, args=(config.site['rar_limit'],))
                rar_p.start()

            if rar_p:
                rar_p.join()

            if imdb_p:
                imdb_p.join()

            if tvrage_p:
                tvrage_p.join()

            if nfo_p:
                nfo_p.join()

            # wait for the configured amount of time between cycles
            log.info('Sleeping for {:d} seconds...'.format(config.site['update_wait']))
            time.sleep(config.site['update_wait'])
        else:
            log.info('No groups active, cancelling start.py...')
            break