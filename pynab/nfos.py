import gzip
import pymongo
import regex

import pynab.nzbs
import pynab.util

from pynab import log
from pynab.db import db, fs
from pynab.server import Server

NFO_MAX_FILESIZE = 50000

NFO_REGEX = [
    regex.compile('((?>\w+[.\-_])+(?:\w+-\d*[a-zA-Z][a-zA-Z0-9]*))', regex.I),

]

def attempt_parse(nfo):
    potential_names = []

    for regex in NFO_REGEX:
        result = regex.search(nfo)
        if result:
            potential_names.append(result.group(0))

    return potential_names


def get(nfo_id):
    """Retrieves and un-gzips an NFO from GridFS."""
    if nfo_id:
        return gzip.decompress(fs.get(nfo_id).read())
    else:
        return None


def process(limit=5, category=0):
    """Process releases for NFO parts and download them."""
    log.info('Checking for NFO segments...')

    with Server() as server:
        query = {'nfo': None}
        if category:
            query['category._id'] = int(category)

        for release in db.releases.find(query).limit(limit).sort('posted', pymongo.DESCENDING).batch_size(50):
            log.debug('Checking for NFO in {}...'.format(release['search_name']))
            nzb = pynab.nzbs.get_nzb_dict(release['nzb'])

            if nzb:
                nfos = []
                if nzb['nfos']:
                    for nfo in nzb['nfos']:
                        if not isinstance(nfo['segments']['segment'], list):
                            nfo['segments']['segment'] = [nfo['segments']['segment'], ]
                        for part in nfo['segments']['segment']:
                            if int(part['@bytes']) > NFO_MAX_FILESIZE:
                                continue
                            nfos.append(part)

                if nfos:
                    for nfo in nfos:
                        try:
                            article = server.get(release['group']['name'], [nfo['#text'], ])
                        except:
                            article = None

                        if article:
                            data = gzip.compress(article.encode('utf-8'))
                            nfo_file = fs.put(data, filename='.'.join([release['name'], 'nfo', 'gz']))

                            if nfo_file:
                                db.releases.update({'_id': release['_id']}, {
                                    '$set': {
                                        'nfo': nfo_file
                                    }
                                })
                                log.info('Grabbed and saved NFO for: {}'.format(release['name']))
                                break
                        else:
                            log.debug('Error retrieving NFO.')
                            continue
                else:
                    log.debug('No NFOs found in this release.')
                    db.releases.update({'_id': release['_id']}, {
                        '$set': {
                            'nfo': False
                        }
                    })