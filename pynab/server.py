import nntplib
import re
import time
import datetime
import math

import dateutil.parser
import pytz

from pynab import log
import config


class Server:
    def __init__(self):
        self.connection = None

    def group(self, group_name):
        if not self.connection:
            self.connect()

        try:
            response, count, first, last, name = self.connection.group(group_name)
        except nntplib.NNTPError:
            log.error('Problem sending group command to server.')
            return False

        return response, count, first, last, name

    def connect(self):
        """Creates a connection to a news server."""
        log.info('Attempting to connect to news server...')

        # i do this because i'm lazy
        ssl = config.news.pop('ssl', False)

        # TODO: work out how to enable compression (no library support?)
        try:
            if ssl:
                self.connection = nntplib.NNTP_SSL(**config.news)
            else:
                self.connection = nntplib.NNTP(**config.news)
        except nntplib.NNTPError as e:
            log.error('Could not connect to news server: ' + e.response)
            return False

        log.info('Connected!')
        return True

    def scan(self, group_name, first, last):
        """Scan a group for segments and return a list."""
        log.info('Collecting parts {0:d} to {1:d} from {2}...'.format(first, last, group_name))

        start = time.clock()

        try:
            # grab the headers we're after
            self.connection.group(group_name)
            count, overviews = self.connection.over((first, last))
        except nntplib.NNTPError:
            return None

        messages = {}
        ignored = 0
        received = []
        for (id, overview) in overviews:
            # keep track of which messages we received so we can
            # optionally check for ones we missed later
            received.append(id)

            # get the current segment number
            results = re.findall('\((\d+)[\/](\d+)\)', overview['subject'])

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
                    message = {
                        'subject': nntplib.decode_header(subject),
                        'posted': dateutil.parser.parse(overview['date']),
                        'posted_by': nntplib.decode_header(overview['from']),
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

        log.info(
            'Received {:d} articles of {:d} with {:d} ignored.'
            .format(len(received), last - first + 1, ignored)
        )

        # TODO: implement re-checking of missed messages, or maybe not
        # most parts that get ko'd these days aren't coming back anyway
        messages_missed = list(set(range(first, last)) - set(received))

        end = time.clock()
        log.info('Time elapsed: {:.2f}s'.format(end - start))

        return messages

    def post_date(self, group_name, article):
        log.debug('Retrieving date of article {:d}'.format(article))
        try:
            self.connection.group(group_name)
            _, articles = self.connection.over('{0:d}-{0:d}'.format(article))
        except nntplib.NNTPError as e:
            log.warning('Error with news server: {0}'.format(e))
            return None

        try:
            art_num, overview = articles[0]
        except IndexError:
            log.warning('Server was missing article {:d}.'.format(article))

            # if the server is missing an article, it's usually part of a large group
            # so skip along quickishly, the datefinder will autocorrect itself anyway
            return self.post_date(group_name, article + int(article * 0.001))

        if art_num and overview:
            return dateutil.parser.parse(overview['date'])
        else:
            return None

    def days_old(self, date):
        return (datetime.datetime.now(pytz.utc) - date).days

    def day_to_post(self, group_name, days):
        log.debug('Finding post {0:d} days old in group {1}...'.format(days, group_name))

        _, count, first, last, _ = self.connection.group(group_name)
        target_date = datetime.datetime.now(pytz.utc) - datetime.timedelta(days)

        first_date = self.post_date(group_name, first)
        last_date = self.post_date(group_name, last)

        if first_date and last_date:
            if target_date < first_date:
                log.warning('First available article is newer than target date, starting from first available.')
                return first
            elif target_date > last_date:
                log.warning('Target date is more recent than newest article. Try a longer backfill.')
                return False
            log.debug('Searching for post where goal: {0}, first: {0}, last: {0}'
            .format(target_date, first_date, last_date)
            )

            upper = last
            lower = first
            interval = math.floor((upper - lower) * 0.5)
            next_date = last_date

            log.debug('Start: {:d} End: {:d} Interval: {:d}'.format(lower, upper, interval))

            while self.days_old(next_date) < days:
                skip = 1
                temp_date = self.post_date(group_name, upper - interval)
                while temp_date > target_date:
                    upper = upper - interval - (skip - 1)
                    log.debug('New upperbound: {:d} is {:d} days old.'
                    .format(upper, self.days_old(temp_date))
                    )
                    skip *= 2
                    temp_date = self.post_date(group_name, upper - interval)

                interval = math.ceil(interval / 2)
                if interval <= 0:
                    break
                skip = 1
                log.debug('Set interval to {:d} articles.'.format(interval))

                next_date = self.post_date(group_name, upper - 1)
                while not next_date:
                    upper = upper - skip
                    skip *= 2
                    log.debug('Article was lost, getting next: {:d}'.format(upper))
                    next_date = self.post_date(group_name, upper - 1)

            log.debug('Article is {:d} which is {:d} days old.'.format(upper, self.days_old(next_date)))
            return upper
        else:
            log.error('Could not get group information.')
            return False




