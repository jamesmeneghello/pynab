import gzip
import re

from mako.template import Template
from mako import exceptions
from pynab.db import fs, db
from pynab import log
import pynab


def create(gid, name, binary):
    log.debug('Creating NZB {0}.nzb.gz and storing it to GridFS...'.format(gid))
    if binary['category_id']:
        category = db.categories.find_one({'id': binary['category_id']})
    else:
        category = None

    xml = ''
    try:
        tpl = Template(filename='D:/Dropbox/Code/pynab/templates/nzb.mako')
        xml = tpl.render(version=pynab.__version__, name=name, category=category, binary=binary)
    except:
        log.error('Failed to create NZB: {0}'.format(exceptions.text_error_template().render()))
        return None

    return fs.put(gzip.compress(xml.encode('utf-8')), filename='.'.join([gid, 'nzb', 'gz']))


def parse_xref(xref):
    groups = []
    raw_groups = xref.split(' ')
    for raw_group in raw_groups:
        result = re.search('^([a-z0-9\.\-_]+):(\d+)?$', raw_group, re.I)
        if result:
            groups.append(result.group(1))
    return groups