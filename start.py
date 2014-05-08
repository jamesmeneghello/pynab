import argparse
import concurrent.futures
import time
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


def update(group_name):
    try:
        return pynab.groups.update(group_name)
    except Exception as e:
        log.critical(traceback.format_exc())
        raise Exception


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

    while True:
        # refresh the db session each iteration, just in case
        with db_session() as db:
            active_groups = [group.name for group in db.query(Group).filter(Group.active==True).all()]
            if active_groups:
                with concurrent.futures.ProcessPoolExecutor(config.scan.get('update_threads', None)) as executor:
                    # if maxtasksperchild is more than 1, everything breaks
                    # they're long processes usually, so no problem having one task per child
                    result = [executor.submit(update, active_group) for active_group in active_groups]
                    #result = executor.map(update, active_groups)
                    for r in concurrent.futures.as_completed(result):
                        data = r.result()

                # process binaries
                pynab.binaries.process()

                # process releases
                pynab.releases.process()

                # clean up dead binaries
                dead_time = pytz.utc.localize(datetime.datetime.now()) - datetime.timedelta(days=config.scan.get('dead_binary_age', 3))
                dead_binaries = db.query(Binary).filter(Binary.posted<=dead_time).delete()
                log.info('start: deleted {} dead binaries'.format(dead_binaries))
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
