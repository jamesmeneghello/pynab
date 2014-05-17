import concurrent.futures
import time
import traceback
import psycopg2.extensions

from pynab import log
from pynab.db import db_session, Release, engine

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


def process_tvrage():
    try:
        return pynab.tvrage.process(500)
    except Exception as e:
        log.critical(traceback.format_exc())
        raise Exception


def process_nfos():
    try:
        return pynab.nfos.process(500)
    except Exception as e:
        log.critical(traceback.format_exc())
        raise Exception


def process_rars():
    try:
        return pynab.rars.process(200)
    except Exception as e:
        log.critical(traceback.format_exc())
        raise Exception


def process_imdb():
    try:
        return pynab.imdb.process(500)
    except Exception as e:
        log.critical(traceback.format_exc())
        raise Exception


if __name__ == '__main__':
    log.info('postprocess: starting post-processing...')

    # start with a quick post-process
    log.info('postprocess: starting with a quick post-process to clear out the cruft that\'s available locally...')
    scripts.quick_postprocess.local_postprocess()

    while True:
        with db_session() as db:
            # delete passworded releases first so we don't bother processing them
            if config.postprocess.get('delete_passworded', True):
                query = db.query(Release)
                if config.postprocess.get('delete_potentially_passworded', True):
                    query = query.filter(Release.passworded=='MAYBE')

                query = query.filter(Release.passworded=='YES')
                deleted = query.delete()
                log.info('postprocess: deleted {} passworded releases'.format(deleted))

            # delete any nzbs that don't have an associated release
            # and delete any releases that don't have an nzb
            #TODO

            with concurrent.futures.ThreadPoolExecutor(4) as executor:
                threads = []

                # grab and append tvrage data to tv releases
                if config.postprocess.get('process_tvrage', True):
                    threads.append(executor.submit(process_tvrage))

                if config.postprocess.get('process_imdb', True):
                    threads.append(executor.submit(process_imdb))

                # grab and append nfo data to all releases
                if config.postprocess.get('process_nfos', True):
                    threads.append(executor.submit(process_nfos))

                # check for passwords, file count and size
                if config.postprocess.get('process_rars', True):
                    threads.append(executor.submit(process_rars))

                for t in concurrent.futures.as_completed(threads):
                    data = t.result()

            # rename misc->other and all ebooks
            scripts.rename_bad_releases.rename_bad_releases(8010)
            scripts.rename_bad_releases.rename_bad_releases(7020)

            if config.postprocess.get('delete_bad_releases', False):
                log.info('Deleting bad releases...')
                db.query(Release).filter(Release.unwanted==True).delete()


            # vacuum the segments, parts and binaries tables
            log.info('start: vacuuming relevant tables...')
            conn = engine.connect()
            conn.connection.connection.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
            conn.execute('VACUUM releases')
            conn.execute('VACUUM metablack')
            conn.execute('VACUUM episodes')
            conn.execute('VACUUM tvshows')
            conn.execute('VACUUM movies')
            conn.execute('VACUUM nfos')
            conn.execute('VACUUM files')
            conn.close()

        # wait for the configured amount of time between cycles
        postprocess_wait = config.postprocess.get('postprocess_wait', 1)
        log.info('sleeping for {:d} seconds...'.format(postprocess_wait))
        time.sleep(postprocess_wait)