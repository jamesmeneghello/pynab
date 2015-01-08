import gzip
import os
import datetime
import regex
import sys
import io
import pytz
from xml.sax.saxutils import escape, quoteattr

from lxml import etree, html
from xml.etree import cElementTree as cet

from pynab.db import db_session, NZB, Category, Release, Group
from pynab import log
import pynab
import pynab.binaries

XPATH_FILE = etree.XPath('file/@subject')
XPATH_SEGMENT = etree.XPath('segments/segment')
XPATH_BYTES = etree.XPath('//@bytes')

nfo_regex = regex.compile('[ "\(\[].*?\.(nfo|ofn)[ "\)\]]', regex.I)
sfv_regex = regex.compile('[ "\(\[].*?\.(sfv|vfs)[ "\)\]]', regex.I)
rar_regex = regex.compile('.*\W(?:part0*1|(?!part\d+)[^.]+)\.(rar|001)[ "\)\]]', regex.I)
rar_part_regex = regex.compile('\.(rar|r\d{2,3})(?!\.)', regex.I)
metadata_regex = regex.compile('\.(par2|vol\d+\+|sfv|nzb)', regex.I)
par2_regex = regex.compile('\.par2(?!\.)', regex.I)
par_vol_regex = regex.compile('vol\d+\+', regex.I)
zip_regex = regex.compile('\.zip(?!\.)', regex.I)
nzb_regex = regex.compile('\.nzb(?!\.)', regex.I)


def get_size(nzb):
    """Returns the size of a release (in bytes) as given by the NZB, compressed."""
    try:
        # using the html parser here instead of the straight lxml might be slower
        # but some of the nzbs spewed forth by newznab are broken and contain
        # non-xml entities, ie. &sup2;
        # this breaks the normal lxml parser
        tree = html.fromstring(gzip.decompress(nzb.data))
    except Exception as e:
        log.critical('nzbs: problem parsing XML with lxml: {}'.format(e))
        return None

    size = 0
    for bytes in XPATH_BYTES(tree):
        try:
            size += int(bytes)
        except:
            # too bad, there was a problem
            return 0

    return size


def filexml_to_dict(element):
    segments = []
    for segment in XPATH_SEGMENT(element):
        s = {
            'size': segment.get('bytes'),
            'segment': segment.get('number'),
            'message_id': segment.text
        }
        segments.append(s)

    return {
        'posted_by': element.get('poster'),
        'posted': element.get('date'),
        'subject': element.get('subject'),
        'segments': segments
    }


def get_nzb_details(nzb):
    """Returns a JSON-like Python dict of NZB contents, including extra information
    such as a list of any nfos/rars that the NZB references."""

    try:
        # using the html parser here instead of the straight lxml might be slower
        # but some of the nzbs spewed forth by newznab are broken and contain
        # non-xml entities, ie. &sup2;
        # this breaks the normal lxml parser
        tree = html.fromstring(gzip.decompress(nzb.data))
    except Exception as e:
        log.critical('nzbs: problem parsing XML with lxml: {}'.format(e))
        return None

    nfos = []
    sfvs = []
    rars = []
    pars = []
    zips = []

    rar_count = 0
    par_count = 0

    for file_subject in XPATH_FILE(tree):
        if rar_part_regex.search(file_subject):
            rar_count += 1
        if nfo_regex.search(file_subject) and not metadata_regex.search(file_subject):
            nfos.append(filexml_to_dict(file_subject.getparent()))
        if sfv_regex.search(file_subject):
            sfvs.append(filexml_to_dict(file_subject.getparent()))
        if rar_regex.search(file_subject) and not metadata_regex.search(file_subject):
            rars.append(filexml_to_dict(file_subject.getparent()))
        if par2_regex.search(file_subject):
            par_count += 1
            if not par_vol_regex.search(file_subject):
                pars.append(filexml_to_dict(file_subject.getparent()))
        if zip_regex.search(file_subject) and not metadata_regex.search(file_subject):
            zips.append(filexml_to_dict(file_subject.getparent()))

    return {
        'nfos': nfos,
        'sfvs': sfvs,
        'rars': rars,
        'pars': pars,
        'zips': zips,
        'rar_count': rar_count,
        'par_count': par_count,
    }


def create(name, parent_category_name, binary):
    """Create the NZB, store it in GridFS and return the ID
    to be linked to the release."""

    xml = io.StringIO()
    xml.write('<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE nzb PUBLIC "-//newzBin//DTD NZB 1.1//EN" "http://www.newzbin.com/DTD/nzb/nzb-1.1.dtd">\n'
        '<nzb>\n'
        '<head><meta type="category">{}</meta><meta type="name">{}</meta></head>\n'.format(parent_category_name, escape(name))
    )

    for part in binary.parts:
        if sys.version_info >= (3, 3):
            timestamp = '{:.0f}'.format(part.posted.replace(tzinfo=pytz.utc).timestamp())
        else:
            timestamp = '{:.0f}'.format(int(part.posted.replace(tzinfo=pytz.utc).strftime("%s")))

        xml.write('<file poster={} date={} subject={}>\n<groups>'.format(
            quoteattr(binary.posted_by),
            quoteattr(timestamp),
            quoteattr('{0} (1/{1:d})'.format(part.subject, part.total_segments))
        ))

        for group in pynab.binaries.parse_xref(binary.xref):
            xml.write('<group>{}</group>\n'.format(group))

        xml.write('</groups>\n<segments>\n')
        for segment in part.segments:
            xml.write('<segment bytes="{}" number="{}">{}</segment>\n'.format(
                segment.size,
                segment.segment,
                escape(segment.message_id)
            ))
        xml.write('</segments>\n</file>\n')
    xml.write('</nzb>')

    nzb = NZB()
    nzb.data = gzip.compress(xml.getvalue().encode('utf-8'))

    return nzb


def import_nzb_file(filepath):
    file, ext = os.path.splitext(filepath)

    if ext == '.gz':
        f = gzip.open(filepath, 'rt', encoding='utf-8', errors='ignore')
    else:
        f = open(filepath, 'r', encoding='utf-8', errors='ignore')

    return import_nzb(filepath, f.read())


def import_nzb(name, nzb_data):
    """Import an NZB and directly load it into releases."""

    release = {'added': pytz.utc.localize(datetime.datetime.now()), 'size': None, 'spotnab_id': None,
               'completion': None, 'grabs': 0, 'passworded': None, 'file_count': None, 'tvrage': None,
               'tvdb': None, 'imdb': None, 'nfo': None, 'tv': None, 'total_parts': 0}

    try:
        for event, elem in cet.iterparse(io.StringIO(nzb_data)):
            if 'meta' in elem.tag:
                release[elem.attrib['type']] = elem.text
            if 'file' in elem.tag:
                release['total_parts'] += 1
                release['posted'] = elem.get('date')
                release['posted_by'] = elem.get('poster')
            if 'group' in elem.tag and 'groups' not in elem.tag:
                release['group_name'] = elem.text
    except Exception as e:
        log.error('nzb: error parsing NZB files: file appears to be corrupt.')
        return False

    if 'name' not in release:
        log.error('nzb: failed to import nzb: {0}'.format(name))
        return False

    # check that it doesn't exist first
    with db_session() as db:
        r = db.query(Release).filter(Release.name == release['name']).first()
        if not r:
            r = Release()
            r.name = release['name']
            r.search_name = release['name']

            r.posted = release['posted']
            r.posted_by = release['posted_by']

            if 'posted' in release:
                r.posted = datetime.datetime.fromtimestamp(int(release['posted']), pytz.utc)
            else:
                r.posted = None

            if 'category' in release:
                parent, child = release['category'].split(' > ')

                category = db.query(Category).filter(Category.name == parent).filter(Category.name == child).first()
                if category:
                    r.category = category
                else:
                    r.category = None
            else:
                r.category = None

            # make sure the release belongs to a group we have in our db
            if 'group_name' in release:
                group = db.query(Group).filter(Group.name == release['group_name']).first()
                if not group:
                    log.error(
                        'nzb: could not add release - group {0} doesn\'t exist.'.format(release['group_name']))
                    return False
                r.group = group

            # rebuild the nzb, gzipped
            nzb = NZB()
            nzb.data = gzip.compress(nzb_data.encode('utf-8'))
            r.nzb = nzb

            db.merge(r)

            return True
        else:
            log.error('nzb: release already exists: {0}'.format(release['name']))
            return False

