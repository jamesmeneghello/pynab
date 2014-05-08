import argparse
import multiprocessing
import time
import logging
import pytz
import datetime
import traceback

from pynab import log, log_descriptor
from pynab.db import db_session, Group, Binary

import pynab.groups
import pynab.binaries
import pynab.releases
import pynab.tvrage
import pynab.rars
import pynab.nfos
import pynab.imdb
import config


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


def daemonize(pidfile):
    try:
        import traceback
        from daemonize import Daemonize

        fds = []
        if log_descriptor:
            fds = [log_descriptor]

        daemon = Daemonize(app='pynab', pid=pidfile, action=main, keep_fds=fds)
        daemon.start()
    except SystemExit:
        raise
    except:
        log.critical(traceback.format_exc())


def main():
    log.info('starting update...')

    # print MP log as well
    multiprocessing.log_to_stderr().setLevel(logging.DEBUG)

    while True:
        # refresh the db session each iteration, just in case
        with db_session() as db:
            active_groups = [group.name for group in db.query(Group).filter(Group.active==True).all()]
            if active_groups:
                # if maxtasksperchild is more than 1, everything breaks
                # they're long processes usually, so no problem having one task per child
                pool = multiprocessing.Pool(processes=config.scan.get('update_threads', 4), maxtasksperchild=1)
                result = pool.map_async(update, active_groups)
                try:
                    result.get()
                except Exception as e:
                    mp_error(e)

                pool.terminate()
                pool.join()

                # process binaries
                pynab.binaries.process()

                # process releases
                pynab.releases.process()

                # clean up dead binaries
                dead_time = pytz.utc.localize(datetime.datetime.now()) - datetime.timedelta(days=config.scan.get('dead_binary_age', 3))
                db.query(Binary).filter(Binary.posted<=dead_time).delete()
            else:
                log.info('no groups active, cancelling start.py...')
                break

        # wait for the configured amount of time between cycles
        update_wait = config.scan.get('update_wait', 300)
        log.info('sleeping for {:d} seconds...'.format(update_wait))
        time.sleep(update_wait)

        
        
if __name__ == '__main__':
    argparser = argparse.ArgumentParser(description="Pynab main indexer script")
    argparser.add_argument('-d', '--daemonize', action='store_true', help='run as a daemon')
    argparser.add_argument('-p', '--pid-file', help='pid file (when -d)')

    args = argparser.parse_args()

    if args.daemonize:
        pidfile = args.pid_file or config.scan.get('pid_file')
        if not pidfile:
            log.error("A pid file is required to run as a daemon, please supply one either in the config file '{}' or as argument".format(config.__file__))
        else:
            daemonize(pidfile)
    else:
        main()
