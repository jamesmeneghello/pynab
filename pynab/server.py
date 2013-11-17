import lib.nntplib as nntplib
import regex
import time
import datetime
import math

import dateutil.parser
import pytz

from pynab import log
import pynab.parts
import pynab.yenc
import config


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
        except nntplib.NNTPError:
            log.error('Problem sending group command to server.')
            return False

        return response, count, first, last, name

    def connect(self, compression=True):
        """Creates a connection to a news server."""
        if not self.connection:
            log.info('Attempting to connect to news server...')

            news_config = config.news.copy()

            # i do this because i'm lazy
            ssl = news_config.pop('ssl', False)

            try:
                if ssl:
                    self.connection = nntplib.NNTP_SSL(compression=compression, **news_config)
                else:
                    self.connection = nntplib.NNTP(compression=compression, **news_config)
            except Exception as e:
                log.error('Could not connect to news server: {}'.format(e))
                return False

            log.info('Connected!')
            return True
        else:
            return True

    def get(self, group_name, messages=None):
        """Get a set of messages from the server for the specified group."""
        log.info('{}: Getting {:d} messages...'.format(group_name, len(messages)))
        data = ''
        if messages:
            try:
                _, total, first, last, _ = self.connection.group(group_name)
                log.debug('{}: Total articles in group: {:d}'.format(group_name, total))
                for message in messages:
                    article = '<{}>'.format(message)

                    log.debug('{}: Getting article: {}'.format(group_name, article))

                    response, (number, message_id, lines) = self.connection.body(article)
                    res = pynab.yenc.yenc_decode(lines)
                    if res:
                        data += res
                    else:
                        return None
            except nntplib.NNTPError as nntpe:
                log.error('{}: Problem retrieving messages from server: {}.'.format(group_name, nntpe))
                return None

            return data
        else:
            log.error('{}: No messages were specified.'.format(group_name))
            return None

    def scan(self, group_name, first, last):
        """Scan a group for segments and return a list."""
        log.info('{}: Collecting parts {:d} to {:d}...'.format(group_name, first, last))

        start = time.clock()

        try:
            # grab the headers we're after
            self.connection.group(group_name)
            status, overviews = self.connection.over((first, last))
        except nntplib.NNTPError as nntpe:
            log.debug('NNTP Error.')
            return None

        messages = {}
        ignored = 0
        received = []
        for (id, overview) in overviews:
            # keep track of which messages we received so we can
            # optionally check for ones we missed later
            received.append(id)

            # get the current segment number
            results = regex.findall('\((\d+)[\/](\d+)\)', overview['subject'])

            # it might match twice, so just get the last one
            # the first is generally the part number
            if results:
                (segment_number, total_segments) = results[-1]
            else:
                # if there's no match at all, it's probably not a binary
                ignored += 1
                continue

            # assuming everything didn't fuck up, continue
            if int(segment_number) > 0 and int(total_segments) > 0:
                # strip the segment number off the subject so
                # we can match binary parts together
                subject = overview['subject'].replace(
                    '(' + str(segment_number) + '/' + str(total_segments) + ')', ''
                ).strip()

                # this is spammy as shit, for obvious reasons
                #pynab.log.debug('Binary part found: ' + subject)

                # build the segment, make sure segment number and size are ints
                segment = {
                    'message_id': overview['message-id'][1:-1],
                    'segment': int(segment_number),
                    'size': int(overview[':bytes']),
                }

                # if we've already got a binary by this name, add this segment
                if subject in messages:
                    messages[subject]['segments'][segment_number] = segment
                    messages[subject]['available_segments'] += 1
                else:
                    # dateutil will parse the date as whatever and convert to UTC
                    # some subjects/posters have odd encoding, which will break pymongo
                    # so we make sure it doesn't
                    message = {
                        'subject': nntplib.decode_header(subject).encode('utf-8', 'surrogateescape').decode('latin-1'),
                        'posted': dateutil.parser.parse(overview['date']),
                        'posted_by': nntplib.decode_header(overview['from']).encode('utf-8', 'surrogateescape').decode(
                            'latin-1'),
                        'group_name': group_name,
                        'xref': overview['xref'],
                        'total_segments': int(total_segments),
                        'available_segments': 1,
                        'segments': {segment_number: segment, },
                    }

                    messages[subject] = message
            else:
                # :getout:
                ignored += 1

        # instead of checking every single individual segment, package them first
        # so we typically only end up checking the blacklist for ~150 parts instead of thousands
        blacklist = [k for k in messages if pynab.parts.is_blacklisted(k, group_name)]
        blacklisted_parts = len(blacklist)
        total_parts = len(messages)
        for k in blacklist:
            del messages[k]

        log.info(
            '{}: Received {:d} articles of {:d}, forming {:d} parts with {:d} ignored and {:d} blacklisted.'
            .format(group_name, len(received), last - first + 1, total_parts, ignored, blacklisted_parts)
        )

        # TODO: implement re-checking of missed messages, or maybe not
        # most parts that get ko'd these days aren't coming back anyway
        messages_missed = list(set(range(first, last)) - set(received))

        end = time.clock()
        log.info('Time elapsed: {:.2f}s'.format(end - start))

        return messages

    def post_date(self, group_name, article):
        """Retrieves the date of the specified post."""
        log.debug('{}: Retrieving date of article {:d}'.format(group_name, article))

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
                log.warning('{}: Server was missing article {:d}.'.format(group_name, article))

                # if the server is missing an article, it's usually part of a large group
                # so skip along quickishly, the datefinder will autocorrect itself anyway
                #article += int(article * 0.001)
                article += 1
                i += 1
                continue

            if art_num and overview:
                return dateutil.parser.parse(overview['date']).astimezone(pytz.utc)
            else:
                return None

    def day_to_post(self, group_name, days):
        """Converts a datetime to approximate article number for the specified group."""
        log.debug('{}: Finding post {:d} days old...'.format(group_name, days))

        _, count, first, last, _ = self.connection.group(group_name)
        target_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(days)

        first_date = self.post_date(group_name, first)
        last_date = self.post_date(group_name, last)

        if first_date and last_date:
            if target_date < first_date:
                log.warning(
                    '{}: First available article is newer than target date, starting from first available.'.format(
                        group_name))
                return first
            elif target_date > last_date:
                log.warning(
                    '{}: Target date is more recent than newest article. Try a longer backfill.'.format(group_name))
                return False
            log.debug('{}: Searching for post where goal: {}, first: {}, last: {}'
            .format(group_name, target_date, first_date, last_date)
            )

            upper = last
            lower = first
            interval = math.floor((upper - lower) * 0.5)
            next_date = last_date

            log.debug('{}: Start: {:d} End: {:d} Interval: {:d}'.format(group_name, lower, upper, interval))

            while self.days_old(next_date) < days:
                skip = 1
                temp_date = self.post_date(group_name, upper - interval)
                if temp_date:
                    while temp_date > target_date:
                        upper = upper - interval - (skip - 1)
                        log.debug('{}: New upperbound: {:d} is {:d} days old.'
                        .format(group_name, upper, self.days_old(temp_date))
                        )
                        skip *= 2
                        temp_date = self.post_date(group_name, upper - interval)

                interval = math.ceil(interval / 2)
                if interval <= 0:
                    break
                skip = 1
                log.debug('{}: Set interval to {:d} articles.'.format(group_name, interval))

                next_date = self.post_date(group_name, upper - 1)
                if next_date:
                    while not next_date:
                        upper = upper - skip
                        skip *= 2
                        log.debug('{}: Article was lost, getting next: {:d}'.format(group_name, upper))
                        next_date = self.post_date(group_name, upper - 1)

            log.debug('{}: Article is {:d} which is {:d} days old.'.format(group_name, upper, self.days_old(next_date)))
            return upper
        else:
            log.error('{}: Could not get group information.'.format(group_name))
            return False

    @staticmethod
    def days_old(date):
        """Returns the age of the given date, in days."""
        return (datetime.datetime.now(pytz.utc) - date).days