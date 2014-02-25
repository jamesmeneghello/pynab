import multiprocessing
import time
import logging

from pynab import log
from pynab.db import db

import pynab.groups
import pynab.binaries
import pynab.releases
import pynab.tvrage
import pynab.rars
import pynab.nfos
import pynab.imdb

import scripts.quick_postprocess
import scripts.rename_bad_releases

import config

def mp_error(msg, *args):
    return multiprocessing.get_logger().error(msg, *args)


def process_tvrage():
    pynab.tvrage.process(500)


def process_nfos():
    pynab.nfos.process(500)


def process_rars():
    pynab.rars.process(500)


def process_imdb():
    pynab.imdb.process(500)


if __name__ == '__main__':
    log.info('Starting post-processing...')

    # print MP log as well
    multiprocessing.log_to_stderr().setLevel(logging.DEBUG)

    # take care of REQ releases first
    for release in db.releases.find({'search_name': {'$regex': 'req', '$options': '-i'}}):
        pynab.releases.strip_req(release)

    # start with a quick post-process
    log.info('Starting with a quick post-process to clear out the cruft that\'s available locally...')
    scripts.quick_postprocess.local_postprocess()

    while True:
        # grab and append tvrage data to tv releases
        tvrage_p = None
        if config.postprocess.get('process_tvrage'):
            tvrage_p = multiprocessing.Process(target=process_tvrage)
            tvrage_p.start()

        imdb_p = None
        if config.postprocess.get('process_imdb'):
            imdb_p = multiprocessing.Process(target=process_imdb)
            imdb_p.start()

        # grab and append nfo data to all releases
        nfo_p = None
        if config.postprocess.get('process_nfos'):
            nfo_p = multiprocessing.Process(target=process_nfos)
            nfo_p.start()

        # check for passwords, file count and size
        rar_p = None
        if config.postprocess.get('process_rars'):
            rar_p = multiprocessing.Process(target=process_rars)
            rar_p.start()

        if rar_p:
            rar_p.join()

        if imdb_p:
            imdb_p.join()

        if tvrage_p:
            tvrage_p.join()

        if nfo_p:
            nfo_p.join()

        # rename misc->other and all ebooks
        scripts.rename_bad_releases.rename_bad_releases(8010)
        scripts.rename_bad_releases.rename_bad_releases(7020)

        if config.postprocess.get('delete_bad_releases'):
            pass
            #log.info('Deleting bad releases...')
            # not confident in this yet

        # wait for the configured amount of time between cycles
        postprocess_wait = config.postprocess.get('postprocess_wait', 1)
        log.info('Sleeping for {:d} seconds...'.format(postprocess_wait))
        time.sleep(postprocess_wait)