import gzip
import pymongo

import pynab.nzbs

from pynab import log
from pynab.db import db, fs
from pynab.server import Server

NFO_MAX_FILESIZE = 50000


def get(nfo_id):
    """Retrieves and un-gzips an NFO from GridFS."""
    return gzip.decompress(fs.get(nfo_id).read())


def process(limit=5):
    """Process releases for NFO parts and download them."""
    log.info('Checking for NFO segments...')

    with Server() as server:
        for release in db.releases.find({'nfo': None}).limit(limit).sort('posted', pymongo.ASCENDING):
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
                        article = server.get(release['group']['name'], [nfo['#text'], ])
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