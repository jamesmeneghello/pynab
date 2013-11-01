import gzip
import sys
import os
import xml.etree.cElementTree as cet
import hashlib
import uuid
import datetime
import regex

import pytz
import xmltodict
from mako.template import Template
from mako import exceptions

from pynab.db import fs, db
from pynab import log
import pynab

nfo_regex = '[ "\(\[].*?\.(nfo|ofn)[ "\)\]]'
rar_regex = '.*\W(?:part0*1|(?!part\d+)[^.]+)\.(rar|001)[ "\)\]]'
rar_part_regex = '\.(rar|r\d{2,3})(?!\.)'
metadata_regex = '\.(par2|vol\d+\+|sfv|nzb)'
par2_regex = '\.par2(?!\.)'
par_vol_regex = 'vol\d+\+'
zip_regex = '\.zip(?!\.)'


def get_nzb_dict(nzb_id):
    """Returns a JSON-like Python dict of NZB contents, including extra information
    such as a list of any nfos/rars that the NZB references."""
    data = xmltodict.parse(gzip.decompress(fs.get(nzb_id).read()))

    nfos = []
    rars = []
    pars = []
    rar_count = 0
    par_count = 0
    zip_count = 0

    if 'file' not in data['nzb']:
        return None

    if not isinstance(data['nzb']['file'], list):
        data['nzb']['file'] = [data['nzb']['file'], ]

    for part in data['nzb']['file']:
        if regex.search(rar_part_regex, part['@subject'], regex.I):
            rar_count += 1
        if regex.search(nfo_regex, part['@subject'], regex.I) and not regex.search(metadata_regex, part['@subject'], regex.I):
            nfos.append(part)
        if regex.search(rar_regex, part['@subject'], regex.I) and not regex.search(metadata_regex, part['@subject'], regex.I):
            rars.append(part)
        if regex.search(par2_regex, part['@subject'], regex.I):
            par_count += 1
            if not regex.search(par_vol_regex, part['@subject'], regex.I):
                pars.append(part)
        if regex.search(zip_regex, part['@subject'], regex.I) and not regex.search(metadata_regex, part['@subject'], regex.I):
            zip_count += 1

    data['nfos'] = nfos
    data['rars'] = rars
    data['pars'] = pars
    data['rar_count'] = rar_count
    data['par_count'] = par_count
    data['zip_count'] = zip_count

    return data


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
    """Import an NZB and directly load it into releases."""
    file, ext = os.path.splitext(filepath)

    if ext == '.gz':
        f = gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore')
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

            release['status'] = 2

            if 'posted' in release:
                release['posted'] = datetime.datetime.fromtimestamp(int(release['posted']), pytz.utc)
            else:
                release['posted'] = None

            if 'category' in release:
                parent, child = release['category'].split(' > ')

                parent_category = db.categories.find_one({'name': parent})
                if parent_category:
                    child_category = db.categories.find_one({'name': child, 'parent_id': parent_category['_id']})

                    if child_category:
                        release['category'] = child_category
                        release['category']['parent'] = parent_category
                    else:
                        release['category'] = None
                else:
                    release['category'] = None
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

