import lib.nntplib as nntplib
import regex
import time
import datetime
import random
import socket

import dateutil.parser
import pytz

from pynab import log
from pynab.db import db_session, Blacklist
import pynab.parts
import pynab.yenc
import config

SEGMENT_REGEX = regex.compile('\((\d+)[\/](\d+)\)', regex.I)


class AuthException(Exception):
    pass


class Server:
    def __init__(self):
        self.connection = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection:
            self.connection.quit()

    def group(self, group_name):
        self.connect()

        try:
            response, count, first, last, name = self.connection.group(group_name)
        except Exception as e:
            log.error('server: couldn\'t send group command')
            return None, False, None, None, None

        return response, count, first, last, name

    def connect(self, compression=True):
        """Creates a connection to a news server."""
        if not config.news.get('user') or not config.news.get('password'):
            raise AuthException('no username or password supplied')

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
        self.connect()

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
        self.connect()

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
        except Exception as e:
            log.error('server: [{}]: nntp error'.format(group_name))
            log.error('server: suspected dead nntp connection, restarting')

            self.connection.quit()
            self.connect()
            return self.scan(group_name, first, last, message_ranges)

        parts = {}
        messages = []
        ignored = 0

        if overviews:
            with db_session() as db:
                blacklists = db.query(Blacklist).filter(Blacklist.status==True).all()
                for blacklist in blacklists:
                    db.expunge(blacklist)

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
                try:
                    size = int(overview[':bytes'])
                except:
                    # TODO: cull this later
                    log.debug('server: bad message: {}'.format(overview))
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
                        'size': size
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

        log.info('server: {}: retrieved {} - {} in {:.2f}s [{} recv, {} pts, {} ign, {} blk]'.format(
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
        self.connect()

        art_num = 0
        overview = None

        try:
            self.connection.group(group_name)
            art_num, overview = self.connection.head('{0:d}'.format(article))
        except nntplib.NNTPError as e:
            log.debug('server: unable to get date of message {}: {}'.format(article, e))
            # leave this alone - we don't expect any data back
            return None

        if art_num and overview:
            # overview[0] = article number
            # overview[1] = message-id
            # overview[2] = headers
            for header in overview[2]:
                date_header = ''

                if 'X-Server-Date:' in header.decode():
                    continue
                elif 'NNTP-Posting-Date:' in header.decode():
                    date_header = header.decode().replace('NNTP-Posting-Date: ', '')
                elif 'Date:' in header.decode():
                    date_header = header.decode().replace('Date: ', '')

                if date_header:
                    try:
                        date = dateutil.parser.parse(date_header)
                    except Exception as e:
                        log.error('server: date parse failed while dating message: {}'.format(e))
                        return None

                    try:
                        date = pytz.utc.localize(date)
                    except:
                        # no problem, it's already localised
                        pass

                    return date
        else:
            return None

    def day_to_post(self, group_name, days):
        """Converts a datetime to approximate article number for the specified group."""
        self.connect()

        log.info('server: finding post {} days old...'.format(days))

        _, count, first, last, _ = self.connection.group(group_name)

        # get first, last and target dates
        candidate_post = None
        target_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(days)
        bottom_date = self.post_date(group_name, first)
        top_date = self.post_date(group_name, last)
        bottom = first
        top = last

        # iterative, obviously
        while True:
            # do something like a binary search
            # find the percentage-point of target date between first and last dates
            # ie. start |-------T---| end = ~70%
            # so we'd find the post number ~70% through the message count
            try:
                target = target_date - bottom_date
                total = top_date - bottom_date
            except:
                log.error('server: nntp server problem while getting first/last article dates')
                return None

            perc = target.total_seconds() / total.total_seconds()

            while True:
                candidate_post = int(abs(bottom + ((top - bottom) * perc)))
                candidate_date = self.post_date(group_name, candidate_post)
                if candidate_date:
                    break
                else:
                    addition = (random.choice([-1, 1]) / 100) * perc
                    if perc + addition > 1.0:
                        perc -= addition
                    elif perc - addition < 0.0:
                        perc += addition
                    else:
                        perc += addition

            # tolerance sliding scale, about 0.1% rounded to the nearest day
            # we don't need a lot of leeway, since this is a lot faster than previously
            tolerance = round(days * 0.001)
            if abs(target_date - candidate_date) < datetime.timedelta(days=tolerance):
                break

            if candidate_date > target_date:
                top = candidate_post
                top_date = candidate_date
            else:
                bottom = candidate_post
                bottom_date = candidate_date

        return candidate_post

    @staticmethod
    def days_old(date):
        """Returns the age of the given date, in days."""
        return (datetime.datetime.now(pytz.utc) - date).days
