import concurrent.futures
import time
import traceback
import datetime

import psycopg2.extensions
import pytz

from pynab import log
from pynab.db import db_session, Release, engine, Blacklist, Group, MetaBlack, NZB, NFO, SFV
import pynab.groups
import pynab.binaries
import pynab.releases
import pynab.tvrage
import pynab.rars
import pynab.nfos
import pynab.sfvs
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


def process_sfvs():
    try:
        return pynab.sfvs.process(500)
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
    # scripts.quick_postprocess.local_postprocess()

    while True:
        with db_session() as db:
            # delete passworded releases first so we don't bother processing them
            if config.postprocess.get('delete_passworded', True):
                query = db.query(Release)
                if config.postprocess.get('delete_potentially_passworded', True):
                    query = query.filter((Release.passworded == 'MAYBE') | (Release.passworded == 'YES'))
                else:
                    query = query.filter(Release.passworded == 'YES')
                deleted = query.delete()
                db.commit()
                log.info('postprocess: deleted {} passworded releases'.format(deleted))
            '''
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

                # grab and append sfv data to all releases
                if config.postprocess.get('process_sfvs', False):
                    threads.append(executor.submit(process_sfvs))

                # check for passwords, file count and size
                if config.postprocess.get('process_rars', True):
                    threads.append(executor.submit(process_rars))

                for t in concurrent.futures.as_completed(threads):
                    data = t.result()
            '''
            # rename misc->other and all ebooks
            scripts.rename_bad_releases.rename_bad_releases(8010)
            scripts.rename_bad_releases.rename_bad_releases(7020)

            # do a postproc deletion of any enabled blacklists
            # assuming it's enabled, of course
            if config.postprocess.get('delete_blacklisted_releases'):
                deleted = 0
                for blacklist in db.query(Blacklist).filter(Blacklist.status == True).all():
                    # remap subject to name, since normal blacklists operate on binaries
                    # this is on releases, and the attribute changes
                    field = 'search_name' if blacklist.field == 'subject' else blacklist.field

                    # filter by:
                    #   group_name should match the blacklist's
                    #   <field> should match the blacklist's regex
                    #   <field> is determined by blacklist's field (usually subject/name)
                    #   date (optimisation)
                    query = db.query(Release).filter(Release.group_id.in_(
                        db.query(Group.id).filter(Group.name.op('~*')(blacklist.group_name)).subquery()
                    )).filter(getattr(Release, field).op('~*')(blacklist.regex))
                    if config.postprocess.get('delete_blacklisted_days'):
                        query = query.filter(Release.posted >= (datetime.datetime.now(pytz.utc) - datetime.timedelta(
                            days=config.postprocess.get('delete_blacklisted_days'))))
                    deleted += query.delete(False)
                log.info('postprocess: deleted {} blacklisted releases'.format(deleted))
                db.commit()

            if config.postprocess.get('delete_bad_releases', False):
                deletes = db.query(Release).filter(Release.unwanted == True).delete()
                log.info('postprocess: deleted {} bad releases'.format(deletes))
                db.commit()

            # delete any orphan metablacks
            log.info('postprocess: deleting orphan metablacks...')
            db.query(MetaBlack).filter(
                (MetaBlack.movie == None) &
                (MetaBlack.tvshow == None) &
                (MetaBlack.rar == None) &
                (MetaBlack.nfo == None) &
                (MetaBlack.sfv == None)
            ).delete(synchronize_session='fetch')

            # delete any orphan nzbs
            log.info('postprocess: deleting orphan nzbs...')
            db.query(NZB.id).filter(NZB.release==None).delete(synchronize_session='fetch')

            # delete any orphan nfos
            log.info('postprocess: deleting orphan nfos...')
            db.query(NFO.id).filter(NFO.release==None).delete(synchronize_session='fetch')

            # delete any orphan sfvs
            log.info('postprocess: deleting orphan sfvs...')
            db.query(SFV.id).filter(SFV.release==None).delete(synchronize_session='fetch')

            db.commit()

            # vacuum the segments, parts and binaries tables
            log.info('postprocess: vacuuming relevant tables...')
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
        postprocess_wait = config.postprocess.get('postprocess_wait', 300)
        log.info('sleeping for {:d} seconds...'.format(postprocess_wait))
        time.sleep(postprocess_wait)
