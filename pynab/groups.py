from intspan import intspan
from sqlalchemy.sql.expression import bindparam

from pynab import log
from pynab.db import db_session, Group, Miss
from pynab.server import Server
import pynab.parts
import config
import time

MESSAGE_LIMIT = config.scan.get('message_scan_limit', 20000)


def backfill(group_name, date=None):
    log.info('group: {}: backfilling group'.format(group_name))

    server = Server()
    _, count, first, last, _ = server.group(group_name)

    if count:
        if date:
            target_article = server.day_to_post(group_name, server.days_old(date))
        else:
            target_article = server.day_to_post(group_name, config.scan.get('backfill_days', 10))

        with db_session() as db:
            group = db.query(Group).filter(Group.name==group_name).one()

            if group:
                # if the group hasn't been updated before, quit
                if not group.first:
                    log.error('group: {}: run a normal update prior to backfilling'.format(group_name))
                    if server.connection:
                        server.connection.quit()
                    return False

                # if the first article we have is lower than the target
                if target_article >= group.first:
                    log.info('group: {}: nothing to do, we already have the target post'.format(group_name))
                    if server.connection:
                        server.connection.quit()
                    return True

                # or if the target is below the server's first
                if target_article < first:
                    target_article = first

                total = group.first - target_article
                end = group.first - 1
                start = end - MESSAGE_LIMIT + 1
                if target_article > start:
                    start = target_article

                retries = 0
                while True:
                    status, parts, messages, missed = server.scan(group_name, first=start, last=end)

                    if status and parts:
                        pynab.parts.save_all(parts)
                        group.first = start
                        db.commit()
                    elif status and not parts:
                        # there were ignored messages and we didn't get anything to save
                        pass
                    else:
                        log.error('group: {}: problem updating group - trying again'.format(group_name))
                        retries += 1
                        # keep trying the same block 3 times, then skip
                        if retries <= 3:
                            continue

                    if start == target_article:
                        if server.connection:
                            server.connection.quit()
                        return True
                    else:
                        end = start - 1
                        start = end - MESSAGE_LIMIT + 1
                        if target_article > start:
                            start = target_article
            else:
                log.error('group: {}: group doesn\'t exist in db.'.format(group_name))
                if server.connection:
                    server.connection.quit()
                return False
    else:
        log.error('backfill: unable to send group command - connection dead?')
        return False


def update(group_name):
    log.info('group: {}: updating group'.format(group_name))

    server = Server()
    _, count, first, last, _ = server.group(group_name)

    if count:
        with db_session() as db:
            group = db.query(Group).filter(Group.name==group_name).one()
            if group:
                # if the group has been scanned before
                if group.last:
                    # pick up where we left off
                    start = group.last + 1

                    # if our last article is newer than the server's, something's wrong
                    if last < group.last:
                        log.error('group: {}: last article {:d} on server is older than the local {:d}'.format(group_name, last,
                                                                                                        group.last))
                        if server.connection:
                            try:
                                server.connection.quit()
                            except:
                                pass
                        return False
                else:
                    # otherwise, start from x days old
                    log.info('group: {}: determining a start point for the group'.format(group_name))

                    start = server.day_to_post(group_name, config.scan.get('new_group_scan_days', 5))
                    if not start:
                        log.error('group: {}: couldn\'t determine a start point for group'.format(group_name))
                        if server.connection:
                            try:
                                server.connection.quit()
                            except:
                                pass
                        return False
                    else:
                        group.first = start
                        db.commit()

                # either way, we're going upwards so end is the last available
                end = last

                # if total > 0, we have new parts
                total = end - start + 1

                # this has been removed, because certain groups (looking at you,
                # a.b.multimedia and probably boneless as well) are taking far too
                # long to return a reply and it's literally only used for
                # informational purposes
                """
                start_date = server.post_date(group_name, start)
                end_date = server.post_date(group_name, end)

                if start_date and end_date:
                    total_date = end_date - start_date

                    log.info('group: {}: pulling {} - {} ({}d, {}h, {}m)'.format(
                        group_name,
                        start, end,
                        total_date.days,
                        total_date.seconds // 3600,
                        (total_date.seconds // 60) % 60
                    ))
                else:
                """
                log.info('group: {}: pulling {} - {}'.format(group_name, start, end))

                if total > 0:
                    if not group.last:
                        log.info('group: {}: starting new group with {:d} days and {:d} new parts'
                            .format(group_name, config.scan.get('new_group_scan_days', 5), total))
                    else:
                        log.info('group: {}: group has {:d} new parts.'.format(group_name, total))

                    retries = 0
                    # until we're finished, loop
                    while True:
                        # break the load into segments
                        if total > MESSAGE_LIMIT:
                            if start + MESSAGE_LIMIT > last:
                                end = last
                            else:
                                end = start + MESSAGE_LIMIT - 1

                        if start > end:
                            log.debug('group: {}: start greater than end. aborting run'.format(group_name))
                            if server.connection:
                                server.connection.quit()
                            return False

                        status, parts, messages, missed = server.scan(group_name, first=start, last=end)

                        try:
                            end = max(messages)
                        except:
                            log.error('group: {}: problem updating group ({}-{}) - trying again'.format(group_name, start, end))

                            retries += 1
                            if retries <= 15:
                                time.sleep(retries)
                                continue
                            else:
                                log.error('group: {}: problem updating group. aborting run'.format(group_name))
                                return False

                        # save any missed messages first (if desired)
                        if status and missed and config.scan.get('retry_missed'):
                            save_missing_segments(group_name, missed)

                        # then save normal messages
                        if status and parts:
                            if pynab.parts.save_all(parts):
                                group.last = end
                                db.merge(group)
                                db.commit()
                                retries = 0
                            else:
                                log.error('group: {}: problem saving parts to db'.format(group_name))
                                return False

                        if end == last:
                            log.info('group: {}: update completed'.format(group_name))
                            if server.connection:
                                server.connection.quit()
                            return True
                        else:
                            start = end + 1
                else:
                    log.info('group: {}: no new messages'.format(group_name))
                    if server.connection:
                        server.connection.quit()
                    return True
            else:
                log.error('group: {}: no group in db'.format(group_name))
                if server.connection:
                    server.connection.quit()
                return False
    else:
        log.error('backfill: unable to send group command - connection dead?')
        return False


def save_missing_segments(group_name, missing_segments):
    """Handles any missing segments by mashing them into ranges
    and saving them to the db for later checking."""

    with db_session() as db:
        # we don't want to get the whole db's worth of segments
        # just get the ones in the range we need
        first, last = min(missing_segments), max(missing_segments)

        # get previously-missed parts
        previous_misses = [r for r, in db.query(Miss.message).filter(Miss.message>=first).filter(Miss.message<=last).filter(Miss.group_name==group_name).all()]

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
        expired = db.query(Miss).filter(Miss.attempts >= config.scan.get('miss_retry_limit')).filter(Miss.group_name==group_name).delete()
        db.commit()
        log.info('missing: saved {} misses and deleted {} expired misses'.format(len(new_misses), expired))


def scan_missing_segments(group_name):
    """Scan for previously missed segments."""

    log.info('missing: checking for missed segments')

    with db_session() as db:
        # recheck for anything to delete
        expired = db.query(Miss).filter(Miss.attempts >= config.scan.get('miss_retry_limit')).filter(Miss.group_name==group_name).delete()
        db.commit()
        if expired:
            log.info('missing: deleted {} expired misses'.format(expired))

        # get missing articles for this group
        missing_messages = [r for r, in db.query(Miss.message).filter(Miss.group_name==group_name).all()]

        if missing_messages:
            # mash it into ranges
            missing_ranges = intspan(missing_messages).ranges()

            server = Server()
            server.connect()

            status, parts, messages, missed = server.scan(group_name, message_ranges=missing_ranges)
            if parts:
                # we got some!
                pynab.parts.save_all(parts)
                db.query(Miss).filter(Miss.message.in_(messages)).filter(Miss.group_name==group_name).delete(False)
                db.commit()

            if missed:
                # clear up those we didn't get
                save_missing_segments(group_name, missed)

            if server.connection:
                server.connection.quit()
