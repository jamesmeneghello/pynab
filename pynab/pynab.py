#!/usr/bin/env python
# -*- coding: utf-8 -*-

import nntplib
import re
import datetime
import dateutil.parser
import time
import pprint
import pymongo
import uuid
import hashlib
import gzip
import os.path
import xml.sax.saxutils
import pytz
import config as app_config




def scan(server, group_name, first, last, type='update'):
    print('Collecting parts ' + str(first) + ' to ' + str(last) + '...')

    server.group(group_name)
    count, overviews = server.over((first, last))

    messages = {}
    blacklisted = 0
    ignored = 0
    received = []
    for (id, overview) in overviews:
        received.append(id)
        results = re.findall('\((\d+)[\/](\d+)\)', overview['subject'])

        if results:
            (piece_number, total_pieces) = results[-1]
        else:
            ignored += 1
            continue

        #if is_blacklisted(overview, group_name):
        #   blacklisted_parts += 1
        #   continue

        if int(piece_number) > 0 and int(total_pieces) > 0:
            subject = overview['subject'].replace('(' + str(piece_number) + '/' + str(total_pieces) + ')', '').strip()

            #print('Binary part found: ' + subject)

            piece = {
                'message_id': overview['message-id'][1:-1],
                'piece': int(piece_number),
                'size': int(overview[':bytes']),
                'total_pieces': int(total_pieces)
            }

            if subject in messages:
                messages[subject]['pieces'].append(piece)
            else:
                messages[subject] = {
                    'subject': subject,
                    'total_pieces': int(total_pieces),
                    'date': dateutil.parser.parse(overview['date']),
                    'group_name': group_name,
                    'pieces': [piece, ],
                    'from': overview['from'],
                    'xref': overview['xref']
                }
        else:
            ignored += 1

    print('Received ' + str(len(received)) + ' articles of '
          + str(last - first + 1) + ' with ' + str(ignored) + ' ignored and '
          + str(blacklisted) + ' blacklisted.'
    )

    messages_missed = list(set(range(first, last)) - set(received))

    if type == 'update' and len(received) == 0:
        print('Server did not return any articles for ' + group_name)
        return False

    if len(messages_missed) > 0:
        #TODO: implement re-check of missing parts
        pass

    return messages


def save_binaries(mongo, binaries):
    for subject, binary in binaries.items():
        pieces = binary.pop('pieces')

        mongo.db().binaries.find_and_modify(
            query={
                'subject': binary['subject'],
                'total_pieces': binary['total_pieces'],
                'group_name': binary['group_name'],
                'from': binary['from']
            },
            update={
                '$setOnInsert': {'date': binary['date']},
                '$addToSet': {'pieces': {'$each': pieces}},
                '$inc': {'available_pieces': len(pieces)},
                '$set': {'xref': binary['xref']}
            },
            upsert=True
        )


def prepare_binaries(mongo):
    print('Preparing binaries for release mashing...')

    start = time.clock()
    for regex in mongo.db().regexes.find():
        if re.search('\*$', regex['group_name']):
            search = regex['group_name'][:-1]
            if search == '':
                query = {}
            else:
                query = {'name': {'$regex': '^' + regex['group_name'][:-1]}}
        else:
            query = {'name': regex['group_name']}

        binaries = []
        orphan_binaries = []
        groups = [g['name'] for g in mongo.db().groups.find(query)]

        for binary in mongo.db().binaries.find({'group_name': {'$in': groups}, 'release.name': {'$exists': False}},
                                               exhaust=True):
            # grab flags and strip delims
            r = regex['regex']
            flags = r[r.rfind('/') + 1:]
            r = r[r.find('/') + 1:r.rfind('/')]
            regex_flags = re.I if 'i' in flags else 0

            result = re.search(r, binary['subject'], regex_flags)
            match = result.groupdict() if result else None
            if match:
                # remove whitespace in dict values
                match = {k: v.strip() for k, v in match.items()}

                # fill name if reqid is available
                if match.get('reqid') and not match.get('name'):
                    match['name'] = match['reqid']

                # make sure the regex returns at least some name
                if not match.get('name'):
                    continue

                timediff = pytz.utc.localize(datetime.datetime.now()) \
                           - pytz.utc.localize(binary['date'])


                if not match.get('parts') and timediff.seconds / 60 / 60 > 3:
                    orphan_binaries.append(match['name'])
                    match['parts'] = '01/01'

                if match.get('name') and match.get('parts'):
                    if match['parts'].find('/') == -1:
                        match['parts'] = match['parts'].replace('-', '/').replace('~', '/').replace(' of ', '/')

                    if re.search('repost|re\-?up', match['name'], flags=re.I):
                        result = re.search('repost\d?|re\-?up', binary['subject'], re.I)
                        if result:
                            match['name'] += ' ' + result[0]

                    current, total = match['parts'].split('/')

                    mongo.db().binaries.update({'_id': binary['_id']}, {
                        '$set': {
                            'release.name': match['name'],
                            'part': int(current),
                            'total_parts': int(total),
                            'release.regex_id': regex['_id'],
                            'release.category_id': regex['category_id'],
                            'release.req_id': match.get('reqid')
                        }
                    })

    end = time.clock()

    print('Time elapsed: ')
    print(end - start)


def process_binaries(mongo):

    start = time.clock()

    print('Processing binaries in preparation for release creation...')

    ext_results = mongo.db().binaries.aggregate([
        {'$match': {
            'release.name': {'$exists': True}
        }},
        {'$sort': {
            'date': pymongo.ASCENDING,
            'release.parts.piece': pymongo.ASCENDING
        }},
        {'$group': {
            '_id': {
                'name': '$release.name',
                'regex_id': '$release.regex_id',
                'req_id': '$release.req_id',
                'category_id': '$release.category_id',
                'total_parts': '$total_parts',
                'group_name': '$group_name'
            },
            'available_parts': {
                '$sum': 1
            },
            'part_ids': {
                '$addToSet': '$_id'
            },
            'date': {
                '$last': '$date'
            },
            'from': {
                '$last': '$from'
            }
        }},
        {'$project': {
            'subject': 1,
            'available_parts': 1,
            'part_ids': 1,
            'release': 1,
            'date': 1,
            'from': 1,
            'completed': {
                '$cmp': ['$available_parts', '$_id.total_parts']
            }
        }},
        {'$match': {
            '$or': [{'completed': 0}, {'completed': 1}]
        }}
    ])

    count = 0
    for release in ext_results['result']:
        # prevents shitty single-piece releases
        binaries = release['part_ids']

        # grab every part (and all pieces) for this release
        binary_results = mongo.db().binaries.aggregate([
            {'$match': {
                '_id': {'$in': binaries}
            }},
            {'$project': {
                'completion': {'$cmp': ['$available_pieces', '$total_pieces']}
            }},
            {'$match': {
                'completion': {'$gte': 0}
            }},
            {'$group': {
                '_id': '$release.name',
                'count': {'$sum': 1}
            }},
            {'$match': {
                'count': {'$gte': release['_id']['total_parts']}
            }}
        ])

        if binary_results.get('result'):
            # well, we managed to end up with a release that has enough parts
            # ...maybe

            #TODO: fix release names if allfilled/req in postproc

            #TODO: dupe checking

            #TODO: categorisation
            gid = hashlib.md5(uuid.uuid1().bytes).hexdigest()
            clean_name = clean_release_name(release['_id']['name'])

            pprint.pprint(release)

            mongo.db().releases.update(
                {
                    'search_name': release['_id']['name'],
                    'posted': release['date']
                },
                {
                    '$setOnInsert': {
                        'id': gid,
                        'added': pytz.utc.localize(datetime.datetime.now()),
                        'size': None,
                        'spotnab_id': None,
                        'completion': None,
                        'grabs': 0,
                        'passworded': None,
                        'file_count': None,
                        'tvrage': None,
                        'tvdb': None,
                        'imdb': None,
                        'nfo': None,
                        'tv': None,
                    },
                    '$set': {
                        'name': clean_name,
                        'search_name': clean_name,
                        'total_parts': len(release['part_ids']),
                        'posted': release['date'],
                        'posted_by': release['from'],
                        'status': 1,
                        'updated': pytz.utc.localize(datetime.datetime.now()),
                        'group_id': mongo.db().groups.find_one({'name': release['_id']['group_name']})['_id'],
                        'category_id': release['_id']['category_id']
                    }
                },
                upsert=True
            )
            create_nzb(mongo, gid, clean_name, release)

    end = time.clock()

    print('Time elapsed: ')
    print(end - start)

def clean_release_name(name):
    chars = ['#', '@', '$', '%', '^', '§', '¨', '©', 'Ö']

    for c in chars:
        name = name.replace(c, '')

    return name.replace('_', ' ')


def create_nzb(mongo, gid, name, release):
    nzb_dir = 'C:\\temp\\nzbs'

    full_path = os.path.join(nzb_dir, gid) +  '.nzb.gz'

    with gzip.open(full_path, 'wb') as nzb:
        nzb.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        nzb.write(b'<!DOCTYPE nzb PUBLIC "-//newzBin//DTD NZB 1.1//EN" "http://www.newzbin.com/DTD/nzb/nzb-1.1.dtd">\n')
        nzb.write(b'<nzb xmlns="http://www.newzbin.com/DTD/2003/nzb">\n\n')
        nzb.write(b'<head>\n')

        if release['_id']['category_id']:
            cat_name = mongo.db().categories.find_one({'_id': release['_id']['category_id']})['name']

            nzb.write(('<meta type=\"category\">' +
                html_escape(cat_name) +
                '</meta>\n'
            ).encode('utf-8'))

        if name:
            nzb.write(('<meta type=\"name\">' +
                html_escape(name) +
                '</meta>\n'
            ).encode('utf-8'))

        nzb.write(b'</head>\n\n')

        for part in mongo.db().binaries.find({'_id': {'$in': release['part_ids']}}).sort([('part', pymongo.ASCENDING)]):
            nzb.write(('<file poster=\"' + html_escape(release['from']) +
                '\" date=\"' + str(int(release['date'].replace(tzinfo=pytz.utc).timestamp())) +
                '\" subject=\"' + html_escape(part['subject']) +
                ' (1/' + str(part['available_pieces']) + ')\">\n'
            ).encode('utf-8'))

            groups = parse_xref(part['xref'])

            nzb.write(b' <groups>\n')
            for group in groups:
                nzb.write(('  <group>' + group + '</group>\n').encode('utf-8'))
            nzb.write(b' </groups>\n')

            nzb.write(b' <segments>\n')
            for piece in sorted(part['pieces'], key=lambda k: k['piece']):
                nzb.write(('  <segment bytes=\"' + str(piece['size']) +
                           '\" number=\"' + str(piece['piece']) + '\">' +
                           html_escape(piece['message_id']) +
                           '  </segment>\n'
                ).encode('utf-8'))

            nzb.write(b' </segments>\n')
            nzb.write(b' </file>\n')

        nzb.write(('<!-- generated by pynab ' + app_config.site['version'] + '-->\n').encode('utf-8'))
        nzb.write(b'</nzb>')

def html_escape(string):
    return xml.sax.saxutils.escape(string, {'"':'&quot;', '\'':'&#039;'})

def parse_xref(xref):
    groups = []
    raw_groups = xref.split(' ')
    for raw_group in raw_groups:
        result = re.search('^([a-z0-9\.\-_]+):(\d+)?$', raw_group, re.I)
        if result:
            groups.append(result.group(1))

    return groups
