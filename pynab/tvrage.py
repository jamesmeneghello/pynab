import unicodedata
import difflib
import datetime
import time
from collections import defaultdict

import regex
import roman
import requests
import xmltodict
import pytz
from lxml import etree

from pynab.db import db_session, Release, Category, TvShow, MetaBlack, Episode, DataLog, windowed_query
from pynab import log
import pynab.util
import config


PROCESS_CHUNK_SIZE = 500


TVRAGE_FULL_SEARCH_URL = 'http://services.tvrage.com/feeds/full_search.php'


# use compiled xpaths and regex for speedup
XPATH_SHOW = etree.XPath('//show')
XPATH_NAME = etree.XPath('name/text()')
XPATH_AKA = etree.XPath('akas/aka/text()')
XPATH_LINK = etree.XPath('link/text()')
XPATH_COUNTRY = etree.XPath('country/text()')

RE_LINK = regex.compile('tvrage\.com\/((?!shows)[^\/]*)$', regex.I)


def process(limit=None, online=True):
    """Processes [limit] releases to add TVRage information."""
    expiry = datetime.datetime.now(pytz.utc) - datetime.timedelta(config.postprocess.get('fetch_blacklist_duration', 7))
    api_session = requests.Session()

    with db_session() as db:
        # clear expired metablacks
        db.query(MetaBlack).filter(MetaBlack.tvshow != None).filter(MetaBlack.time <= expiry).delete(
            synchronize_session='fetch')

        query = db.query(Release).filter((Release.tvshow == None) | (Release.episode == None)).join(Category).filter(
            Category.parent_id == 5000)

        if online:
            query = query.filter(Release.tvshow_metablack_id == None)

        query = query.order_by(Release.posted.desc())

        if limit:
            releases = query.limit(limit)
        else:
            releases = windowed_query(query, Release.id, PROCESS_CHUNK_SIZE)

        for release in releases:
            method = ''

            show = parse_show(release.search_name)
            if not show:
                show = parse_show(release.name)

            if show:
                if release.tvshow:
                    rage = release.tvshow
                else:
                    rage = db.query(TvShow).filter(
                        TvShow.name.ilike('%'.join(show['clean_name'].split(' ')))
                    ).first()

                if not rage and 'and' in show['clean_name']:
                    rage = db.query(TvShow).filter(TvShow.name == show['clean_name'].replace(' and ', ' & ')).first()

                if rage:
                    method = 'local'
                elif not rage and online:
                    rage_data = search(api_session, show)
                    if rage_data:
                        method = 'online'
                        rage = db.query(TvShow).filter(TvShow.id == rage_data['showid']).first()
                        if not rage:
                            rage = TvShow(id=rage_data['showid'], name=rage_data['name'], country=rage_data['country'])
                            db.add(rage)

                    # wait slightly so we don't smash the api
                    time.sleep(1)

                if rage:
                    log.info('tvrage: add {} [{}]'.format(
                        method,
                        release.search_name
                    ))

                    e = db.query(Episode).filter(Episode.tvshow_id == rage.id).filter(
                        Episode.series_full == show['series_full']).first()
                    if not e:
                        e = Episode(
                            season=show.get('season'),
                            episode=show.get('episode'),
                            series_full=show.get('series_full'),
                            air_date=show.get('air_date'),
                            year=show.get('year'),
                            tvshow_id=rage.id
                        )
                    release.tvshow = rage
                    release.tvshow_metablack_id = None
                    release.episode = e
                    db.add(release)
                elif not rage and online:
                    log.debug('tvrage: [{}] - tvrage failed: {}'.format(
                        release.search_name,
                        'no show found (online)'
                    ))

                    mb = MetaBlack(tvshow=release, status='ATTEMPTED')
                    db.add(mb)
                else:
                    log.debug('tvrage: [{}] - tvrage failed: {}'.format(
                        release.search_name,
                        'no show found (local)'
                    ))
            else:
                log.debug('tvrage: [{}] - tvrage failed: {}'.format(
                    release.search_name,
                    'no suitable regex for show name'
                ))
                db.add(MetaBlack(tvshow=release, status='IMPOSSIBLE'))
                db.add(DataLog(description='tvrage parse_show regex', data=release.search_name))

            db.commit()


def search(session, show):
    """Search TVRage's online API for show data."""
    try:
        r = session.get(TVRAGE_FULL_SEARCH_URL, params={'show': show['clean_name']})
    except Exception as e:
        log.error(e)
        return None

    content = r.content
    return search_lxml(show, content)


def extract_names(xmlshow):
    """Extract all possible show names for matching from an lxml show tree, parsed from tvrage search"""
    for name in XPATH_NAME(xmlshow):
        yield name
    for aka in XPATH_AKA(xmlshow):
        yield aka
    link = XPATH_LINK(xmlshow)[0]
    link_result = RE_LINK.search(link)
    if link_result:
        for link in link_result.groups():
            yield link


def search_lxml(show, content):
    """Search TVRage online API for show data."""
    try:
        tree = etree.fromstring(content)
    except:
        log.critical('Problem parsing XML with lxml')
        return None

    matches = defaultdict(list)
    # parse show names in the same order as returned by tvrage, first one is usually the good one
    for xml_show in XPATH_SHOW(tree):
        for name in extract_names(xml_show):
            ratio = int(difflib.SequenceMatcher(None, show['clean_name'], clean_name(name)).ratio() * 100)
            if ratio == 100:
                return xmltodict.parse(etree.tostring(xml_show))['show']
            matches[ratio].append(xml_show)

    # if no 100% is found, check highest ratio matches
    for ratio, xml_matches in sorted(matches.items(), reverse=True):
        for xml_match in xml_matches:
            if ratio >= 80:
                return xmltodict.parse(etree.tostring(xml_match))['show']
            elif 80 > ratio > 60:
                if 'country' in show and show['country'] and XPATH_COUNTRY(xml_match):
                    if str.lower(show['country']) == str.lower(XPATH_COUNTRY(xml_match)[0]):
                        return xmltodict.parse(etree.tostring(xml_match))['show']


def clean_name(name):
    """Cleans a show name for searching."""
    name = unicodedata.normalize('NFKD', name)

    name = regex.sub('[._\-]', ' ', name)
    name = regex.sub('[\':!"#*’,()?]', '', name)
    name = regex.sub('\s{2,}', ' ', name)
    name = regex.sub('\[.*?\]', '', name)

    replace_chars = {
        '$': 's',
        '&': 'and',
        'ß': 'ss'
    }

    for k, v in replace_chars.items():
        name = name.replace(k, v)

    pattern = regex.compile(r'\b(hdtv|dvd|divx|xvid|mpeg2|x264|aac|flac|bd|dvdrip|10 bit|264|720p|1080p\d+x\d+)\b',
                            regex.I)
    name = pattern.sub('', name)

    return name.lower()


def parse_show(search_name):
    """Parses a show name for show name, season and episode information."""

    # i fucking hate this function and there has to be a better way of doing it
    # named capturing groups in a list and semi-intelligent processing?

    show = {}
    match = pynab.util.Match()
    if match.match('^(.*?)[\. \-]s(\d{1,2})\.?e(\d{1,3})(?:\-e?|\-?e)(\d{1,3})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': [int(match.match_obj.group(3)), int(match.match_obj.group(4))],
        }
    elif match.match('^(.*?)[\. \-]s(\d{2})\.?e(\d{2})(\d{2})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': [int(match.match_obj.group(3)), int(match.match_obj.group(4))],
        }
    elif match.match('^(.*?)[\. \-]s(\d{1,2})\.?e(\d{1,3})\.?', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': int(match.match_obj.group(3)),
        }
    elif match.match('^(.*?)[\. \-]s(\d{1,2})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': 'all',
        }
    elif match.match('^(.*?)[\. \-]s(\d{1,2})d\d{1}\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': 'all',
        }
    elif match.match('^(.*?)[\. \-](\d{1,2})x(\d{1,3})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': int(match.match_obj.group(3)),
        }
    elif match.match('^(.*?)[\. \-](19|20)(\d{2})[\.\-](\d{2})[\.\-](\d{2})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': match.match_obj.group(2) + match.match_obj.group(3),
            'episode': '{}/{}'.format(match.match_obj.group(4), match.match_obj.group(5)),
            'air_date': '{}{}-{}-{}'.format(match.match_obj.group(2), match.match_obj.group(3),
                                            match.match_obj.group(4), match.match_obj.group(5))
        }
    elif match.match('^(.*?)[\. \-](\d{2}).(\d{2})\.(19|20)(\d{2})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': match.match_obj.group(4) + match.match_obj.group(5),
            'episode': '{}/{}'.format(match.match_obj.group(2), match.match_obj.group(3)),
            'air_date': '{}{}-{}-{}'.format(match.match_obj.group(4), match.match_obj.group(5),
                                            match.match_obj.group(2), match.match_obj.group(3))
        }
    elif match.match('^(.*?)[\. \-](\d{2}).(\d{2})\.(\d{2})\.', search_name, regex.I):
        # this regex is particularly awful, but i don't think it gets used much
        # seriously, > 15? that's going to be a problem in 2 years
        if 15 < int(match.match_obj.group(4)) <= 99:
            season = '19' + match.match_obj.group(4)
        else:
            season = '20' + match.match_obj.group(4)

        show = {
            'name': match.match_obj.group(1),
            'season': season,
            'episode': '{}/{}'.format(match.match_obj.group(2), match.match_obj.group(3)),
            'air_date': '{}-{}-{}'.format(season, match.match_obj.group(2), match.match_obj.group(3))
        }
    elif match.match('^(.*?)[\. \-]20(\d{2})\.e(\d{1,3})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': '20' + match.match_obj.group(2),
            'episode': int(match.match_obj.group(3)),
        }
    elif match.match('^(.*?)[\. \-]20(\d{2})\.Part(\d{1,2})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': '20' + match.match_obj.group(2),
            'episode': int(match.match_obj.group(3)),
        }
    elif match.match('^(.*?)[\. \-](?:Part|Pt)\.?(\d{1,2})\.', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': 1,
            'episode': int(match.match_obj.group(2)),
        }
    elif match.match('^(.*?)[\. \-](?:Part|Pt)\.?([ivx]+)', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': 1,
            'episode': roman.fromRoman(str.upper(match.match_obj.group(2)))
        }
    elif match.match('^(.*?)[\. \-]EP?\.?(\d{1,3})', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': 1,
            'episode': int(match.match_obj.group(2)),
        }
    elif match.match('^(.*?)[\. \-]Seasons?\.?(\d{1,2})', search_name, regex.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': 'all'
        }
    elif match.match('^(.+)\s{1,3}(\d{1,3})\s\[([\w\d]+)\]', search_name, regex.I):
        # mostly anime
        show = {
            'name': match.match_obj.group(1),
            'season': 1,
            'episode': int(match.match_obj.group(2))
        }

    if 'name' in show and show['name']:
        # check for country code or name (Biggest Loser Australia etc)
        country = regex.search('[\._ ](US|UK|AU|NZ|CA|NL|Canada|Australia|America)', show['name'], regex.I)
        if country:
            if str.lower(country.group(1)) == 'canada':
                show['country'] = 'CA'
            elif str.lower(country.group(1)) == 'australia':
                show['country'] = 'AU'
            elif str.lower(country.group(1)) == 'america':
                show['country'] = 'US'
            else:
                show['country'] = str.upper(country.group(1))

        show['clean_name'] = clean_name(show['name'])

        if not isinstance(show['season'], int) and len(show['season']) == 4:
            show['series_full'] = '{}/{}'.format(show['season'], show['episode'])
        else:
            year = regex.search('[\._ ](19|20)(\d{2})', search_name, regex.I)
            if year:
                show['year'] = year.group(1) + year.group(2)

            show['season'] = 'S{:02d}'.format(show['season'])

            # check to see what episode ended up as
            if isinstance(show['episode'], list):
                show['episode'] = ''.join(['E{:02d}'.format(s) for s in show['episode']])
            elif isinstance(show['episode'], int):
                show['episode'] = 'E{:02d}'.format(int(show['episode']))
                # if it's a date string, leave it as that

            show['series_full'] = show['season'] + show['episode']

        return show

    return False





