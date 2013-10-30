import re
import unicodedata
import difflib
import datetime
import time
import roman
import requests
import xmltodict
import pytz

from pynab.db import db
from pynab import log
import pynab.util
import config

TVRAGE_FULL_SEARCH_URL = 'http://services.tvrage.com/feeds/full_search.php'


def process(limit=100, online=True):
    """Processes [limit] releases to add TVRage information."""
    log.info('Processing TV episodes to add TVRage data...')

    expiry = datetime.datetime.now(pytz.utc) - datetime.timedelta(config.site['fetch_blacklist_duration'])
    for release in db.releases.find({'tvrage._id': {'$exists': False},
                                     'category.parent_id': 5000,
                                     'tvrage.possible': {'$exists': False},
                                     '$or': [{'tvrage.attempted': {'$exists': False}},
                                             {'tvrage.attempted': {'$lte': expiry}}]}).limit(limit):
        log.info('Processing TV/Rage information for show {}.'.format(release['search_name']))
        show = parse_show(release['search_name'])
        if show:
            db.releases.update({'_id': release['_id']}, {
                '$set': {
                    'tv': show
                }
            })

            rage = db.tvrage.find_one({'name': show['clean_name']})
            if not rage and 'and' in show['clean_name']:
                rage = db.tvrage.find_one({'name': show['clean_name'].replace(' and ', ' & ')})

            if not rage and online:
                log.info('Show not found in local TvRage DB, searching online...')
                rage_data = search(show)
                if rage_data:
                    db.tvrage.update(
                        {'_id': int(rage_data['showid'])},
                        {
                            '$set': {
                                'name': rage_data['name']
                            }
                        },
                        upsert=True
                    )
                    rage = db.tvrage.find_one({'_id': int(rage_data['showid'])})

                # wait slightly so we don't smash the api
                time.sleep(1)

            if rage:
                log.info('TVRage match found, appending TVRage ID to release.')
                db.releases.update({'_id': release['_id']}, {
                    '$set': {
                        'tvrage': rage
                    }
                })
            elif not rage and online:
                log.warning('Could not find TVRage data to associate with release {}.'.format(release['search_name']))
                db.releases.update({'_id': release['_id']}, {
                    '$set': {
                        'tvrage': {
                            'attempted': datetime.datetime.now(pytz.utc)
                        },
                    }
                })
            else:
                log.warning('Could not find local TVRage data to associate with release {}.'.format(release['search_name']))
        else:
            log.warning('Could not parse name for TV data: {}.'.format(release['search_name']))
            db.releases.update({'_id': release['_id']}, {
                '$set': {
                    'tvrage': {
                        'possible': False
                    },
                }
            })


def search(show):
    """Search TVRage online API for show data."""
    try:
        r = requests.get(TVRAGE_FULL_SEARCH_URL, params={'show': show['clean_name']})
        result = xmltodict.parse(r.content)
    except:
        log.error('Problem retrieving TVRage XML. The API is probably down.')
        return None

    # did the api return any shows?
    if 'show' in result['Results']:
        result = result['Results']

        # if we only got 1 match, put it in a list so we can just foreach it regardless
        if 'showid' in result['show']:
            result['show'] = [result['show']]

        matches = {}
        for rage_show in result['show']:
            # do aka matches first so they're most likely to get overwritten
            if 'akas' in rage_show:
                akas = []
                # some of tvrage's return data is stupidly non-standard
                # seriously, does this come from a wiki?
                if 'aka' in rage_show['akas']:
                    if '#text' in rage_show['akas']['aka']:
                        # it's a normal match
                        akas.append(rage_show['akas']['aka']['#text'])
                    elif isinstance(rage_show['akas']['aka'], list):
                        for aka in rage_show['akas']['aka']:
                            if '#text' in aka:
                                akas.append(aka['#text'])
                            else:
                                akas.append(aka)
                    else:
                        akas.append(rage_show['akas']['aka'])

                # check matches in akas
                for aka in akas:
                    ratio = int(difflib.SequenceMatcher(None, show['clean_name'], clean_name(aka)).ratio() * 100)
                    matches[ratio] = rage_show

            # check for link matches
            if 'link' in rage_show:
                link_result = re.search('tvrage\.com\/((?!shows)[^\/]*)$', rage_show['link'], re.I)
                if link_result:
                    ratio = int(difflib.SequenceMatcher(None, show['clean_name'],
                                                        clean_name(link_result.group(1))).ratio() * 100)
                    matches[ratio] = rage_show

            # check for title matches
            ratio = int(difflib.SequenceMatcher(None, show['clean_name'], clean_name(rage_show['name'])).ratio() * 100)
            matches[ratio] = rage_show

        if 100 in matches:
            log.debug('Found 100% match: {}'.format(matches[100]['name']))
            return matches[100]
        else:
            for ratio, match in sorted(matches.items(), reverse=True):
                if ratio >= 80:
                    log.debug('Found {:d}% match: {}'.format(ratio, match['name']))
                    return match
                elif 80 > ratio > 60:
                    if 'country' in show and show['country'] and match['country']:
                        if str.lower(show['country']) == str.lower(match['country']):
                            log.debug('Found {:d}% match: {}'.format(ratio, match['name']))
                            return match

            ratio, highest = sorted(matches.items(), reverse=True)[0]
            log.debug('Highest match was {}% with {}.'.format(ratio, highest['name']))

    log.error('Could not find TVRage match online.')
    return None


def clean_name(name):
    """Cleans a show name for searching (against tvrage)."""
    name = unicodedata.normalize('NFKD', name)

    name = re.sub('[._\-]', ' ', name)
    name = re.sub('[\':!"#*’,()?]', '', name)
    name = re.sub('\s{2,}', ' ', name)

    replace_chars = {
        '$': 's',
        '&': 'and',
        'ß': 'ss'
    }

    for k, v in replace_chars.items():
        name = name.replace(k, v)

    return name


def parse_show(search_name):
    """Parses a show name for show name, season and episode information."""

    # i fucking hate this function and there has to be a better way of doing it
    # named capturing groups in a list and semi-intelligent processing?

    show = {}
    match = pynab.util.Match()
    if match.match('^(.*?)[\. \-]s(\d{1,2})\.?e(\d{1,3})(?:\-e?|\-?e)(\d{1,3})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': [int(match.match_obj.group(3)), int(match.match_obj.group(4))],
        }
    elif match.match('^(.*?)[\. \-]s(\d{2})\.?e(\d{2})(\d{2})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': [int(match.match_obj.group(3)), int(match.match_obj.group(4))],
        }
    elif match.match('^(.*?)[\. \-]s(\d{1,2})\.?e(\d{1,3})\.?', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': int(match.match_obj.group(3)),
        }
    elif match.match('^(.*?)[\. \-]s(\d{1,2})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': 'all',
        }
    elif match.match('^(.*?)[\. \-]s(\d{1,2})d\d{1}\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': 'all',
        }
    elif match.match('^(.*?)[\. \-](\d{1,2})x(\d{1,3})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': int(match.match_obj.group(3)),
        }
    elif match.match('^(.*?)[\. \-](19|20)(\d{2})[\.\-](\d{2})[\.\-](\d{2})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': match.match_obj.group(2) + match.match_obj.group(3),
            'episode': '{}/{}'.format(match.match_obj.group(4), match.match_obj.group(5)),
            'air_date': '{}{}-{}-{}'.format(match.match_obj.group(2), match.match_obj.group(3),
                                            match.match_obj.group(4), match.match_obj.group(5))
        }
    elif match.match('^(.*?)[\. \-](\d{2}).(\d{2})\.(19|20)(\d{2})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': match.match_obj.group(4) + match.match_obj.group(5),
            'episode': '{}/{}'.format(match.match_obj.group(2), match.match_obj.group(3)),
            'air_date': '{}{}-{}-{}'.format(match.match_obj.group(4), match.match_obj.group(5),
                                            match.match_obj.group(2), match.match_obj.group(3))
        }
    elif match.match('^(.*?)[\. \-](\d{2}).(\d{2})\.(\d{2})\.', search_name, re.I):
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
    elif match.match('^(.*?)[\. \-]20(\d{2})\.e(\d{1,3})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': '20' + match.match_obj.group(2),
            'episode': int(match.match_obj.group(3)),
        }
    elif match.match('^(.*?)[\. \-]20(\d{2})\.Part(\d{1,2})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': '20' + match.match_obj.group(2),
            'episode': int(match.match_obj.group(3)),
        }
    elif match.match('^(.*?)[\. \-](?:Part|Pt)\.?(\d{1,2})\.', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': 1,
            'episode': int(match.match_obj.group(2)),
        }
    elif match.match('^(.*?)[\. \-](?:Part|Pt)\.?([ivx]+)', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': 1,
            'episode': roman.fromRoman(str.upper(match.match_obj.group(2)))
        }
    elif match.match('^(.*?)[\. \-]EP?\.?(\d{1,3})', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': 1,
            'episode': int(match.match_obj.group(2)),
        }
    elif match.match('^(.*?)[\. \-]Seasons?\.?(\d{1,2})', search_name, re.I):
        show = {
            'name': match.match_obj.group(1),
            'season': int(match.match_obj.group(2)),
            'episode': 'all'
        }
    else:
        log.error('No regex match.')

    if 'name' in show and show['name']:
        # check for country code or name (Biggest Loser Australia etc)
        country = re.search('[\._ ](US|UK|AU|NZ|CA|NL|Canada|Australia|America)', show['name'], re.I)
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
            year = re.search('[\._ ](19|20)(\d{2})', search_name, re.I)
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

    log.error('Could not determine show info from search_name: {}'.format(search_name))
    return False





