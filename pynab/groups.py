from intspan import intspan
from sqlalchemy.sql.expression import bindparam
#from memory_profiler import profile

from pynab import log
from pynab.db import db_session, Group, Miss
from pynab.server import Server
import pynab.parts
import config

#@profile
def scan(group_name, direction='forward', date=None, target=None, limit=None):
    log.info('group: {}: scanning group'.format(group_name))

    with Server() as server:
        _, count, first, last, _ = server.group(group_name)

        if count:
            with db_session() as db:
                group = db.query(Group).filter(Group.name == group_name).first()

                if group:
                    # sort out missing first/lasts
                    if not group.first and not group.last:
                        group.first = last
                        group.last = last
                        direction = 'backward'
                    elif not group.first:
                        group.first = group.last
                    elif not group.last:
                        group.last = group.first

                    # check that our firsts and lasts are valid
                    if group.first < first:
                        log.error('group: {}: first article was older than first on server'.format(group_name))
                        return True
                    elif group.last > last:
                        log.error('group: {}: last article was newer than last on server'.format(group_name))
                        return True

                    db.merge(group)

                    # sort out a target
                    start = 0
                    mult = 0
                    if direction == 'forward':
                        start = group.last
                        target = last
                        mult = 1
                    elif direction == 'backward':
                        start = group.first
                        if not target:
                            target = server.day_to_post(group_name,
                                                    server.days_old(date) if date else config.scan.get('backfill_days',
                                                                                                       10))
                        mult = -1

                    if not target:
                        log.info('group: {}: unable to continue'.format(group_name))
                        return True

                    if group.first <= target <= group.last:
                        log.info('group: {}: nothing to do, already have target'.format(group_name))
                        return True

                    if first > target or last < target:
                        log.error('group: {}: server doesn\'t carry target article'.format(group_name))
                        return True

                    iterations = 0
                    num = config.scan.get('message_scan_limit') * mult
                    for i in range(start, target, num):
                        # set the beginning and ends of the scan to their respective values
                        begin = i + mult
                        end = i + (mult * config.scan.get('message_scan_limit'))

                        # check if the target is before our end
                        if abs(begin) <= abs(target) <= abs(end):
                            # we don't want to overscan
                            end = target

                        # at this point, we care about order
                        # flip them if one is bigger
                        begin, end = (begin, end) if begin < end else (end, begin)

                        status, parts, messages, missed = server.scan(group_name, first=begin, last=end)

                        try:
                            if direction == 'forward':
                                group.last = max(messages)
                            elif direction == 'backward':
                                group.first = min(messages)
                        except:
                            log.error('group: {}: problem updating group ({}-{})'.format(group_name, start, end))
                            return False

                        # don't save misses if we're backfilling, there are too many
                        if status and missed and config.scan.get('retry_missed') and direction == 'forward':
                            save_missing_segments(group_name, missed)

                        if status and parts:
                            if pynab.parts.save_all(parts):
                                db.merge(group)
                                db.commit()
                            else:
                                log.error('group: {}: problem saving parts to db, restarting scan'.format(group_name))
                                return False

                        to_go = abs(target - end)
                        log.info('group: {}: {:.0f} iterations ({} messages) to go'.format(
                                group_name,
                                to_go / config.scan.get('message_scan_limit'),
                                to_go
                            )
                        )

                        parts.clear()
                        del messages[:]
                        del missed[:]

                        iterations += 1

                        if limit and config.scan.get('message_scan_limit') >= limit:
                            log.info(
                                'group: {}: scan limit reached, ending early (will continue later)'.format(group_name))
                            return False

                    log.info('group: {}: scan completed'.format(group_name))
                    return True


def save_missing_segments(group_name, missing_segments):
    """Handles any missing segments by mashing them into ranges
    and saving them to the db for later checking."""

    with db_session() as db:
        # we don't want to get the whole db's worth of segments
        # just get the ones in the range we need
        first, last = min(missing_segments), max(missing_segments)

        # get previously-missed parts
        previous_misses = [r for r, in
                           db.query(Miss.message).filter(Miss.message >= first).filter(Miss.message <= last).filter(
                               Miss.group_name == group_name).all()]

        # find any messages we're trying to get again
        repeats = list(set(previous_misses) & set(missing_segments))

        # update the repeats to include the new attempt
        if repeats:
            stmt = Miss.__table__.update().where(
                Miss.__table__.c.message == bindparam('m')
            ).values(
                attempts=Miss.__table__.c.attempts + 1
            )

            db.execute(stmt, [{'m': m} for m in repeats if m])

        # subtract the repeats from our new list
        new_misses = list(set(missing_segments) - set(repeats))

        # batch-insert the missing messages
        if new_misses:
            db.execute(Miss.__table__.insert(), [
                {
                    'message': m,
                    'group_name': group_name,
                    'attempts': 1
                }
                for m in new_misses
            ])

        # delete anything that's been attempted enough
        expired = db.query(Miss).filter(Miss.attempts >= config.scan.get('miss_retry_limit')).filter(
            Miss.group_name == group_name).delete()
        db.commit()
        log.info('missing: saved {} misses and deleted {} expired misses'.format(len(new_misses), expired))


def scan_missing_segments(group_name):
    """Scan for previously missed segments."""

    log.info('missing: checking for missed segments')

    with db_session() as db:
        # recheck for anything to delete
        expired = db.query(Miss).filter(Miss.attempts >= config.scan.get('miss_retry_limit')).filter(
            Miss.group_name == group_name).delete()
        db.commit()
        if expired:
            log.info('missing: deleted {} expired misses'.format(expired))

        # get missing articles for this group
        missing_messages = [r for r, in db.query(Miss.message).filter(Miss.group_name == group_name).all()]

        if missing_messages:
            # mash it into ranges
            missing_ranges = intspan(missing_messages).ranges()

            server = Server()
            server.connect()

            status, parts, messages, missed = server.scan(group_name, message_ranges=missing_ranges)

            # if we got some missing parts, save them
            if parts:
                pynab.parts.save_all(parts)

            # even if they got blacklisted, delete the ones we got from the misses
            if messages:
                db.query(Miss).filter(Miss.message.in_(messages)).filter(Miss.group_name == group_name).delete(False)

            db.commit()

            if missed:
                # clear up those we didn't get
                save_missing_segments(group_name, missed)

            if server.connection:
                try:
                    server.connection.quit()
                except:
                    pass

