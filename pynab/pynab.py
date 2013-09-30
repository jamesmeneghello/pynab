#!/usr/bin/env python
# -*- coding: utf-8 -*-

import nntplib
import logging
import re
import pprint

logger = logging.getLogger(__name__)

def connect(config):
    ssl = config.pop('ssl', False)
    try:
        if ssl:
            server = nntplib.NNTP_SSL(**config)
        else:
            server = nntplib.NNTP(**config)
    except nntplib.NNTPError as e:
        logger.error('Could not connect to news server: ' + e.response)
        return False

    return server


def scan(server, group_name, first, last, type='update'):
    server.group(group_name)
    count, overviews = server.over((first, last))

    messages = {}
    blacklisted_messages = 0
    ignored_messages = 0
    received_messages = []
    for (id, overview) in overviews:
        received_messages.append(id)

        results = re.findall('\((\d+)[\/](\d+)\)', overview['subject'])

        if results:
            (part_number, total_parts) = results[-1]
        else:
            continue

        #if is_blacklisted(overview, group_name):
        #   blacklisted_parts += 1
        #   continue

        if int(part_number) > 0 and int(total_parts) > 0:
            subject = overview['subject'].replace('(' + str(part_number) + '/' + str(total_parts) + ')', '').strip()

            logger.debug('Binary part found: ' + subject)

            part = {
                'message_id': overview['message-id'][1:-1],
                'part': int(part_number),
                'size': int(overview[':bytes'])
            }

            if subject in messages:
                    messages[subject]['parts'].append(part)
            else:
                messages[subject] = {
                    'subject': subject,
                    'total_parts': int(total_parts),
                    'date': overview['date'],
                    'parts': [part,]
                }
        else:
            ignored_messages += 1

    logger.info('Received ' + str(received_messages) + ' articles of ' + str(last-first+1) + ' with ' + str(ignored_messages))

    messages_missed = list(set(range(first, last)) - set(received_messages))

    if type == 'update' and len(received_messages) == 0:
        logger.error('Server did not return any articles for ' + group_name)
        return False

    if len(messages_missed) > 0:
        #TODO: implement re-check of missing parts
        pass

    return messages