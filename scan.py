"""Pynab Scanner, for indexing groups

Usage:
    pynab.py update [<group>]
    pynab.py backfill [<group>] [--date=<date>]

Options:
    -h --help       Show this screen.
    --version       Show version.
    --date=<date>   The date to backfill to.

"""

import concurrent.futures
import time
import datetime
import traceback

import pytz
import dateutil.parser
from docopt import docopt

from pynab import log, log_init
from pynab.db import db_session, Group, Binary, Miss, Segment, vacuum
import pynab.groups
import pynab.binaries
import pynab.releases
import pynab.rars
import pynab.nfos
import pynab.debug
import pynab.server
import config


def update(group_name):
    try:
        return pynab.groups.scan(group_name, limit=config.scan.get('group_scan_limit', 2000000))
    except pynab.server.AuthException as e:
        log.error('server: {}'.format(e))
    except Exception as e:
        log.error('scan: nntp server is flipping out, hopefully they fix their shit: {}'.format(
            traceback.format_exc(e)
        ))


def backfill(group_name, date=None, target=None):
    if date:
        date = pytz.utc.localize(dateutil.parser.parse(date))
    else:
        date = pytz.utc.localize(datetime.datetime.now() - datetime.timedelta(config.scan.get('backfill_days', 10)))
    try:
        return pynab.groups.scan(group_name, direction='backward', date=date, target=target,
                                 limit=config.scan.get('group_scan_limit', 2000000))
    except Exception as e:
        log.error('scan: nntp server is flipping out, hopefully they fix their shit: {}'.format(
            traceback.format_exc(e)
        ))


def scan_missing(group_name):
    try:
        return pynab.groups.scan_missing_segments(group_name)
    except Exception as e:
        log.error('scan: nntp server is flipping out, hopefully they fix their shit: {}'.format(
            traceback.format_exc(e)
        ))


def process():
    # process binaries
    log.info('scan: processing binaries...')
    pynab.binaries.process()

    # process releases
    log.info('scan: processing releases...')
    pynab.releases.process()


def main(mode='update', group=None, date=None):
    log_init(mode)

    log.info('scan: starting {}...'.format(mode))

    groups = []
    active_groups = {}

    if mode == 'backfill':
        log.info('scan: finding targets for backfill...')
        with pynab.server.Server() as server:
            with db_session() as db:
                if not group:
                    groups = [group.name for group in db.query(Group).filter(Group.active == True).all()]
                else:
                    if db.query(Group).filter(Group.name == group).first():
                        groups = [group]
                for group in groups:
                    target = server.day_to_post(group,
                                                server.days_old(pytz.utc.localize(dateutil.parser.parse(date)))
                                                if date else config.scan.get('backfill_days', 10)
                                                )
                    if target:
                        active_groups[group] = target

    iterations = 0
    while True:
        iterations += 1
        data = []

        # refresh the db session each iteration, just in case
        with db_session() as db:
            if db.query(Segment).count() > config.scan.get('early_process_threshold', 50000000):
                if mode == 'update':
                    log.info('scan: backlog of segments detected, processing first')
                    process()
                else:
                    log.info('scan: backlog of segments detected during backfill, waiting until update has cleared them')
                    time.sleep(config.scan.get('update_wait', 600))
                    continue

            # for scanning, we want to re-check active groups each iteration
            # we don't want to do that for backfilling, though
            if mode == 'update':
                if not group:
                    active_groups = {group.name: None for group in db.query(Group).filter(Group.active == True).all()}
                else:
                    if db.query(Group).filter(Group.name == group).first():
                        active_groups = {group: None}
                    else:
                        log.error('scan: no such group exists')
                        return

            if active_groups:
                with concurrent.futures.ThreadPoolExecutor(config.scan.get('update_threads', None)) as executor:
                    # if maxtasksperchild is more than 1, everything breaks
                    # they're long processes usually, so no problem having one task per child
                    if mode == 'backfill':
                        result = [executor.submit(backfill, active_group, date, target) for active_group, target in active_groups.items()]
                    else:
                        result = [executor.submit(update, active_group) for active_group in active_groups.keys()]

                    for r in concurrent.futures.as_completed(result):
                        data.append(r.result())

                    if mode == 'backfill':
                        if all(data):
                            return

                    # don't retry misses during backfill, it ain't gonna happen
                    if config.scan.get('retry_missed') and not mode == 'backfill':
                        miss_groups = [group_name for group_name, in
                                       db.query(Miss.group_name).group_by(Miss.group_name).all()]
                        miss_result = [executor.submit(scan_missing, miss_group) for miss_group in miss_groups]

                        # no timeout for these, because it could take a while
                        for r in concurrent.futures.as_completed(miss_result):
                            data = r.result()

                db.commit()

                if mode == 'update':
                    process()

                    # clean up dead binaries and parts
                    if config.scan.get('dead_binary_age', 1) != 0:
                        dead_time = pytz.utc.localize(datetime.datetime.now()).replace(
                            tzinfo=None) - datetime.timedelta(days=config.scan.get('dead_binary_age', 3))

                        dead_binaries = db.query(Binary).filter(Binary.posted <= dead_time).delete()
                        db.commit()

                        log.info('scan: deleted {} dead binaries'.format(dead_binaries))
            else:
                log.info('scan: no groups active, cancelling pynab.py...')
                break

            if mode == 'update':
                # vacuum the segments, parts and binaries tables
                log.info('scan: vacuuming relevant tables...')

                if iterations >= config.scan.get('full_vacuum_iterations', 288):
                    # this may look weird, but we want to reset iterations even if full_vacuums are off
                    # so it doesn't count to infinity
                    if config.scan.get('full_vacuum', True):
                        vacuum(mode='scan', full=True)
                    iterations = 0
            else:
                iterations = 0

            db.close()

        # don't bother waiting if we're backfilling, just keep going
        if mode == 'update':
            # wait for the configured amount of time between cycles
            update_wait = config.scan.get('update_wait', 300)
            log.info('scan: sleeping for {:d} seconds...'.format(update_wait))
            time.sleep(update_wait)


if __name__ == '__main__':
    arguments = docopt(__doc__, version=pynab.__version__)
    if arguments['backfill']:
        mode = 'backfill'
    else:
        mode = 'update'

    main(mode=mode, group=arguments['<group>'], date=arguments['--date'])
