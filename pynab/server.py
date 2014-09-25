import lib.nntplib as nntplib
import regex
import time
import datetime
import math
import socket

import dateutil.parser
import pytz

from pynab import log
from pynab.db import db_session, Blacklist
import pynab.parts
import pynab.yenc
import config


SEGMENT_REGEX = regex.compile('\((\d+)[\/](\d+)\)', regex.I)


class Server:
    def __init__(self):
        self.connection = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            try:
                self.connection.quit()
            except Exception as e:
                pass

    def group(self, group_name):
        self.connect()

        try:
            response, count, first, last, name = self.connection.group(group_name)
        except Exception as e:
            log.error('server: could not send group command: {}'.format(e))
            return None, False, None, None, None

        return response, count, first, last, name

    def connect(self, compression=True):
        """Creates a connection to a news server."""
        if not self.connection:
            news_config = config.news.copy()

            # i do this because i'm lazy
            ssl = news_config.pop('ssl', False)

            try:
                if ssl:
                    self.connection = nntplib.NNTP_SSL(compression=compression, **news_config)
                else:
                    self.connection = nntplib.NNTP(compression=compression, **news_config)
            except Exception as e:
                log.error('server: could not connect to news server: {}'.format(e))
                return False

        return True

    def get(self, group_name, messages=None):
        """Get a set of messages from the server for the specified group."""

        data = ''
        if messages:
            try:
                _, total, first, last, _ = self.connection.group(group_name)
                for message in messages:
                    article = '<{}>'.format(message)
                    response, (number, message_id, lines) = self.connection.body(article)
                    res = pynab.yenc.yenc_decode(lines)
                    if res:
                        data += res
                    else:
                        return None
            except nntplib.NNTPError as nntpe:
                log.error('server: [{}]: problem retrieving messages: {}.'.format(group_name, nntpe))
                self.connection = None
                self.connect()
                return None
            except socket.timeout:
                log.error('server: socket timed out, reconnecting')
                self.connection = None
                self.connect()
                return None

            return data
        else:
            return None

    def scan(self, group_name, first=None, last=None, message_ranges=None):
        """Scan a group for segments and return a list."""

        messages_missed = []

        start = time.time()
        try:
            # grab the headers we're after
            self.connection.group(group_name)
            if message_ranges:
                overviews = []
                for first, last in message_ranges:
                    log.debug('server: getting range {}-{}'.format(first, last))
                    status, range_overviews = self.connection.over((first, last))
                    if range_overviews:
                        overviews += range_overviews
                    else:
                        # we missed them
                        messages_missed += range(first, last + 1)

            else:
                status, overviews = self.connection.over((first, last))
        except nntplib.NNTPError as nntpe:
            log.error('server: [{}]: nntp error: {}'.format(group_name, nntpe))
            log.error('server: suspected dead nntp connection, restarting')

            # don't even quit, because that'll still break
            # null the connection and restart it
            self.connection = None
            self.connect()
            return False, None, None, None
        except socket.timeout:
            # backfills can sometimes go for so long that everything explodes
            log.error('server: socket timed out, reconnecting')
            self.connection = None
            self.connect()
            return False, None, None, None

        parts = {}
        messages = []
        ignored = 0

        if overviews:
            with db_session() as db:
                blacklists = db.query(Blacklist).filter(Blacklist.status==True).all()

            for (id, overview) in overviews:
                # keep track of which messages we received so we can
                # optionally check for ones we missed later
                messages.append(id)

                # some messages don't have subjects? who knew
                if 'subject' not in overview:
                    continue

                # get the current segment number
                results = SEGMENT_REGEX.findall(overview['subject'])

                # it might match twice, so just get the last one
                # the first is generally the part number
                if results:
                    (segment_number, total_segments) = results[-1]
                else:
                    # if there's no match at all, it's probably not a binary
                    ignored += 1
                    continue

                # make sure the header contains everything we need
                if ':bytes' not in overview:
                    continue
                elif not overview[':bytes']:
                    continue

                # assuming everything didn't fuck up, continue
                if int(segment_number) > 0 and int(total_segments) > 0:
                    # strip the segment number off the subject so
                    # we can match binary parts together
                    subject = nntplib.decode_header(overview['subject'].replace(
                        '(' + str(segment_number) + '/' + str(total_segments) + ')', ''
                    ).strip()).encode('utf-8', 'replace').decode('latin-1')

                    posted_by = nntplib.decode_header(overview['from']).encode('utf-8', 'replace').decode('latin-1')

                    # generate a hash to perform matching
                    hash = pynab.parts.generate_hash(subject, posted_by, group_name, int(total_segments))

                    # this is spammy as shit, for obvious reasons
                    #pynab.log.debug('Binary part found: ' + subject)

                    # build the segment, make sure segment number and size are ints
                    segment = {
                        'message_id': overview['message-id'][1:-1],
                        'segment': int(segment_number),
                        'size': int(overview[':bytes'])
                    }

                    # if we've already got a binary by this name, add this segment
                    if hash in parts:
                        parts[hash]['segments'][segment_number] = segment
                        parts[hash]['available_segments'] += 1
                    else:
                        # dateutil will parse the date as whatever and convert to UTC
                        # some subjects/posters have odd encoding, which will break pymongo
                        # so we make sure it doesn't
                        try:
                            message = {
                                'hash': hash,
                                'subject': subject,
                                'posted': dateutil.parser.parse(overview['date']),
                                'posted_by': posted_by,
                                'group_name': group_name,
                                'xref': overview['xref'],
                                'total_segments': int(total_segments),
                                'available_segments': 1,
                                'segments': {segment_number: segment, },
                            }

                            parts[hash] = message
                        except Exception as e:
                            log.error('server: bad message parse: {}'.format(e))
                            continue
                else:
                    # :getout:
                    ignored += 1

            # instead of checking every single individual segment, package them first
            # so we typically only end up checking the blacklist for ~150 parts instead of thousands
            blacklist = [k for k, v in parts.items() if pynab.parts.is_blacklisted(v, group_name, blacklists)]
            blacklisted_parts = len(blacklist)
            total_parts = len(parts)
            for k in blacklist:
                del parts[k]
        else:
            total_parts = 0
            blacklisted_parts = 0

        # check for missing messages if desired
        # don't do this if we're grabbing ranges, because it won't work
        if not message_ranges:
            messages_missed = list(set(range(first, last)) - set(messages))

        end = time.time()

        log.info('server: [{}]: retrieved {} - {} in {:.2f}s [{} recv, {} pts, {} ign, {} blk]'.format(
            group_name,
            first, last,
            end - start,
            len(messages),
            total_parts,
            ignored,
            blacklisted_parts
        ))

        # check to see if we at least got some messages - they might've been ignored
        if len(messages) > 0:
            status = True
        else:
            status = False

        return status, parts, messages, messages_missed

    def post_date(self, group_name, article):
        """Retrieves the date of the specified post."""

        i = 0
        while i < 10:
            articles = []

            try:
                self.connection.group(group_name)
                _, articles = self.connection.over('{0:d}-{0:d}'.format(article))
            except nntplib.NNTPError as e:
                log.debug(e)
                # leave this alone - we don't expect any data back
                pass

            try:
                art_num, overview = articles[0]
            except IndexError:
                # if the server is missing an article, it's usually part of a large group
                # so skip along quickishly, the datefinder will autocorrect itself anyway
                article += int(article * 0.0001)
                #article += 1
                i += 1
                continue

            if art_num and overview:
                try:
                    date = dateutil.parser.parse(overview['date']).astimezone(pytz.utc)
                except Exception as e:
                    log.error('server: date parse failed while dating message: {}'.format(e))
                    return None
                return date
            else:
                return None

    def day_to_post(self, group_name, days):
        """Converts a datetime to approximate article number for the specified group."""

        _, count, first, last, _ = self.connection.group(group_name)
        target_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(days)

        first_date = self.post_date(group_name, first)
        last_date = self.post_date(group_name, last)

        if first_date and last_date:
            if target_date < first_date:
                return first
            elif target_date > last_date:
                return False

            upper = last
            lower = first
            interval = math.floor((upper - lower) * 0.5)
            next_date = last_date

            while self.days_old(next_date) < days:
                skip = 1
                temp_date = self.post_date(group_name, upper - interval)
                if temp_date:
                    while temp_date > target_date:
                        upper = upper - interval - (skip - 1)
                        skip *= 2
                        date = self.post_date(group_name, upper - interval)
                        # if we couldn't get the date, skip this one
                        if date:
                            temp_date = date


                interval = math.ceil(interval / 2)
                if interval <= 0:
                    break
                skip = 1

                next_date = self.post_date(group_name, upper - 1)
                if next_date:
                    while not next_date:
                        upper = upper - skip
                        skip *= 2
                        next_date = self.post_date(group_name, upper - 1)

            log.debug('server: {}: article {:d} is {:d} days old.'.format(group_name, upper, self.days_old(next_date)))
            return upper
        else:
            log.error('server: {}: could not get group information.'.format(group_name))
            return False

    @staticmethod
    def days_old(date):
        """Returns the age of the given date, in days."""
        return (datetime.datetime.now(pytz.utc) - date).days