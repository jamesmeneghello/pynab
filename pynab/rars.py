import tempfile
import os
import re

import lib.rar
from pynab import log
from pynab.db import db
import pynab.nzbs
import pynab.releases
from pynab.server import Server
import config


MAYBE_PASSWORDED_REGEX = re.compile('\.(ace|cab|tar|gz|url)$', re.I)
PASSWORDED_REGEX = re.compile('password\.url', re.I)


def check_release_files(server, group_name, nzb):
    """Retrieves rar metadata for release files."""

    rar_files = []
    for rar in nzb['rars']:
        messages = [s['#text'] for s in rar['segments']['segment']]

        data = server.get(group_name, messages)

        if data:
            t = None
            try:
                with tempfile.NamedTemporaryFile('wb', delete=False) as t:
                    t.write(data.encode('ISO-8859-1'))
                    t.flush()
                rar_files += lib.rar.RarFile(t.name).infolist()
            except:
                continue
            finally:
                log.debug('Deleting temporary file {}...'.format(t.name))
                os.remove(t.name)
            break

    passworded = any([r.is_encrypted for r in rar_files])
    file_count = len(rar_files)
    size = sum([r.file_size for r in rar_files])

    return (passworded, file_count, size), rar_files


def process(limit=20):
    """Processes release rarfiles to check for passwords and filecounts. Optionally
    deletes passworded releases."""
    log.info('Checking for passworded releases and deleting them if appropriate...')

    with Server() as server:
        for release in db.releases.find({'passworded': None}).limit(limit):
            nzb = pynab.nzbs.get_nzb_dict(release['nzb'])

            (passworded, file_count, size), rar_files = check_release_files(server, release['group']['name'], nzb)
            if not passworded:
                for file in rar_files:
                    if PASSWORDED_REGEX.search(file.filename):
                        log.debug('Release definitely passworded.')
                        passworded = True
                    elif MAYBE_PASSWORDED_REGEX.search(file.filename):
                        log.debug('Release potentially passworded.')
                        passworded = config.site['delete_potentially_passworded']
            else:
                log.debug('RAR was encrypted.')

            log.info('Adding file data to release: {}'.format(release['name']))

            db.releases.update({'_id': release['_id']}, {
                '$set': {
                    'file_count': file_count,
                    'size': size,
                    'passworded': passworded
                }
            })

    if config.site['delete_passworded']:
        log.info('Deleting passworded releases...')
        db.releases.remove({'passworded': True})