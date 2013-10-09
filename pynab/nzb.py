import gzip
import sys
import os
import xml.etree.cElementTree as cet
import hashlib
import uuid
import datetime
import pytz

from mako.template import Template
from mako import exceptions
from pynab.db import fs, db
from pynab import log
import pynab


def create(gid, name, binary):
    """Create the NZB, store it in GridFS and return the ID
    to be linked to the release."""
    log.debug('Creating NZB {0}.nzb.gz and storing it to GridFS...'.format(gid))
    if binary['category_id']:
        category = db.categories.find_one({'id': binary['category_id']})
    else:
        category = None

    xml = ''
    try:
        tpl = Template(filename='templates/nzb.mako')
        xml = tpl.render(version=pynab.__version__, name=name, category=category, binary=binary)
    except:
        log.error('Failed to create NZB: {0}'.format(exceptions.text_error_template().render()))
        return None

    data = gzip.compress(xml.encode('utf-8'))
    return fs.put(data, filename='.'.join([gid, 'nzb', 'gz'])), sys.getsizeof(data, 0)


def import_nzb(filepath, quick=True):
    file, ext = os.path.splitext(filepath)

    if ext == '.nzb.gz':
        f = gzip.open(filepath, 'r', encoding='utf-8', errors='ignore')
    else:
        f = open(filepath, 'r', encoding='utf-8', errors='ignore')

    if quick:
        release = {'added': pytz.utc.localize(datetime.datetime.now()), 'size': None, 'spotnab_id': None,
                   'completion': None, 'grabs': 0, 'passworded': None, 'file_count': None, 'tvrage': None,
                   'tvdb': None, 'imdb': None, 'nfo': None, 'tv': None, 'total_parts': 0}

        try:
            for event, elem in cet.iterparse(f):
                if 'meta' in elem.tag:
                    release[elem.attrib['type']] = elem.text
                if 'file' in elem.tag:
                    release['total_parts'] += 1
                    release['posted'] = elem.get('date')
                    release['posted_by'] = elem.get('poster')
                if 'group' in elem.tag and 'groups' not in elem.tag:
                    release['group_name'] = elem.text
        except:
            log.error('Error parsing NZB files: file appears to be corrupt.')
            return False

        if 'name' not in release:
            log.error('Failed to import nzb: {0}'.format(filepath))
            return False

        # check that it doesn't exist first
        r = db.releases.find_one({'name': release['name']})
        if not r:
            release['id'] = hashlib.md5(uuid.uuid1().bytes).hexdigest()
            release['search_name'] = release['name']
            release['posted'] = datetime.datetime.fromtimestamp(int(release['posted']), pytz.utc)
            release['status'] = 2

            if 'category' in release:
                parent, child = release['category'].split(' > ')

                parent_category = db.categories.find_one({'name': parent})
                child_category = db.categories.find_one({'name': child, 'parent_id': parent_category['_id']})

                if parent_category and child_category:
                    release['category'] = child_category
                    release['category']['parent'] = parent_category
            else:
                release['category'] = None

            # make sure the release belongs to a group we have in our db
            if 'group_name' in release:
                group = db.groups.find_one({'name': release['group_name']}, {'name': 1})
                if not group:
                    log.error('Could not add release - group {0} doesn\'t exist.'.format(release['group_name']))
                    return False
                release['group'] = group
                del release['group_name']

            # rebuild the nzb, gzipped
            f.seek(0)
            data = gzip.compress(f.read().encode('utf-8'))
            release['nzb'] = fs.put(data, filename='.'.join([release['id'], 'nzb', 'gz']))
            release['nzb_size'] = sys.getsizeof(data, 0)

            try:
                db.releases.insert(release)
            except:
                log.error('Problem saving release: {0}'.format(release))
                return False
            f.close()

            return True
        else:
            log.error('Release already exists: {0}'.format(release['name']))
            return False

