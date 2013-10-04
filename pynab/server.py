import pynab
from pynab.segment import Segment
from pynab.part import Part
import config

import nntplib
import re
import dateutil.parser

class Server:
    def __init__(self):
        self.connection = None

    def connect(self):
        pynab.log.info('Attempting to connect to news server...')

        # i do this because i'm lazy
        ssl = config.news.pop('ssl', False)

        # TODO: work out how to enable compression (no library support?)
        try:
            if ssl:
                self.connection = nntplib.NNTP_SSL(**config.news)
            else:
                self.connection = nntplib.NNTP(**config.news)
        except nntplib.NNTPError as e:
            pynab.log.error('Could not connect to news server: ' + e.response)
            return False

        pynab.log.info('Connected!')

    def scan(self, group_name, first, last):
        pynab.log.info('Collecting parts ' + str(first) + ' to ' + str(last) + '...')

        # grab the headers we're after
        self.connection.group(group_name)
        count, overviews = self.connection.over((first, last))

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
                segment = Segment(
                    overview['message-id'][1:-1],
                    int(segment_number),
                    int(overview[':bytes']),
                )

                # if we've already got a binary by this name, add this segment
                if subject in messages:
                    messages[subject].segments.append(segment)
                else:
                    # dateutil will parse the date as whatever and convert to UTC
                    messages[subject] = Part(
                        subject,
                        dateutil.parser.parse(overview['date']),
                        overview['from'],
                        group_name,
                        overview['xref'],
                        int(total_segments),
                        [segment, ],
                    )
            else:
                # :getout:
                ignored += 1

        pynab.log.info(
            'Received ' + str(len(received)) + ' articles of ' + str(last - first + 1) +
            ' with ' + str(ignored) + ' ignored.'
        )

        # TODO: implement re-checking of missed messages, or maybe not
        # most parts that get ko'd these days aren't coming back anyway
        messages_missed = list(set(range(first, last)) - set(received))

        return messages