import unicodedata
import regex
import roman
import datetime
import pytz
import time

from pynab import log
import pynab.util
from pynab.interfaces.movie import INTERFACES as MOVIE_INTERFACES
from pynab.interfaces.tv import INTERFACES as TV_INTERFACES
from pynab.db import db_session, windowed_query, Release, MetaBlack, Category, Movie, TvShow, DBID, DataLog, Episode

import config


CLEANING_REGEX = regex.compile(r'\b(hdtv|dvd|divx|xvid|mpeg2|x264|aac|flac|bd|dvdrip|10 bit|264|720p|1080p\d+x\d+)\b', regex.I)


def process(type, interfaces=None, limit=None, online=True):
    """
    Process ID fetching for releases.

    :param type: tv/movie
    :param interfaces: interfaces to use or None will use all
    :param limit: optional limit
    :param online: whether to check online apis
    :return:
    """
    expiry = datetime.datetime.now(pytz.utc) - datetime.timedelta(config.postprocess.get('fetch_blacklist_duration', 7))

    with db_session() as db:
        db.query(MetaBlack).filter((MetaBlack.movie != None)|(MetaBlack.tvshow != None)).filter(MetaBlack.time <= expiry).delete(synchronize_session='fetch')

        if type == 'movie':
            query = db.query(Release).filter(Release.movie == None).join(Category).filter(Category.parent_id == 2000)
            if online:
                query = query.filter(Release.movie_metablack_id == None)
        elif type == 'tv':
            query = db.query(Release).filter(Release.tvshow == None).join(Category).filter(Category.parent_id == 5000)
            if online:
                query = query.filter(Release.tvshow_metablack_id == None)
        else:
            raise Exception('wrong release type')

        query = query.order_by(Release.posted.desc())

        if limit:
            releases = query.limit(limit)
        else:
            releases = windowed_query(query, Release.id, config.scan.get('binary_process_chunk_size'))

        if type == 'movie':
            parse_func = parse_movie
            iface_list = MOVIE_INTERFACES
            obj_class = Movie
            attr = 'movie'

            def extract_func(data):
                return {'name': data.get('name'), 'genre': data.get('genre', None), 'year': data.get('year', None)}
        elif type == 'tv':
            parse_func = parse_tv
            iface_list = TV_INTERFACES
            obj_class = TvShow
            attr = 'tvshow'

            def extract_func(data):
                return {'name': data.get('name'), 'country': data.get('country', None)}
        else:
            raise Exception('wrong release type')

        for release in releases:
            data = parse_func(release.search_name)
            if data:
                method = 'local'

                if type == 'movie':
                    q = db.query(Movie).filter(Movie.name.ilike('%'.join(clean_name(data['name']).split(' ')))).filter(Movie.year == data['year'])
                elif type == 'tv':
                    q = db.query(TvShow).filter(TvShow.name.ilike('%'.join(clean_name(data['name']).split(' '))))
                else:
                    q = None

                entity = q.first()
                if not entity and online:
                    method = 'online'
                    ids = {}
                    for iface in iface_list:
                        if interfaces and iface.NAME not in interfaces:
                            continue
                        exists = q.join(DBID).filter(DBID.db==iface.NAME).first()
                        if not exists:
                            id = iface.search(data)
                            if id:
                                ids[iface.NAME] = id
                    if ids:
                        entity = obj_class(**extract_func(data))
                        db.add(entity)

                        for interface_name, id in ids.items():
                            i = DBID()
                            i.db = interface_name
                            i.db_id = id
                            setattr(i, attr, entity)
                            db.add(i)
                if entity:
                    log.info('{}: [{}] - [{}] - data added: {}'.format(
                        attr,
                        release.id,
                        release.search_name,
                        method
                    ))

                    if type == 'tv':
                        # episode processing
                        ep = db.query(Episode).filter(Episode.tvshow_id == entity.id).filter(Episode.series_full == data['series_full']).first()
                        if not ep:
                            ep = Episode(
                                season=data.get('season'),
                                episode=data.get('episode'),
                                series_full=data.get('series_full'),
                                air_date=data.get('air_date'),
                                year=data.get('year'),
                                tvshow=entity
                            )

                        release.episode = ep

                    setattr(release, attr, entity)
                    db.add(release)
                else:
                    log.info('{}: [{}] - data not found: {}'.format(
                        attr,
                        release.search_name,
                        method
                    ))

                    if online:
                        mb = MetaBlack(status='ATTEMPTED')
                        setattr(mb, attr, release)
                        db.add(mb)
            else:
                log.info('movie: [{}] - [{}] - {} data not found: no suitable regex for {} name'.format(
                    attr,
                    release.id,
                    release.search_name,
                    attr
                ))
                mb = MetaBlack(status='IMPOSSIBLE')
                setattr(mb, attr, release)
                db.add(mb)
                db.add(DataLog(description='parse_{} regex'.format(attr), data=release.search_name))

            db.commit()
            time.sleep(1)


def clean_name(name):
    """
    Cleans a show/movie name for searching.

    :param name: release name
    :return: cleaned name
    """

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

    name = CLEANING_REGEX.sub('', name)

    return name.lower()


def parse_tv(search_name):
    """
    Parse a TV show name for episode, season, airdate and name information.

    :param search_name: release name
    :return: show data (dict)
    """

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

    return None


def parse_movie(search_name):
    """
    Parse a movie name into name/year.

    :param search_name: release name
    :return: (name, year)
    """
    result = regex.search('^(?P<name>.*)[\.\-_\( ](?P<year>19\d{2}|20\d{2})', search_name, regex.I)
    if result:
        result = result.groupdict()
        if 'year' not in result:
            result = regex.search(
                '^(?P<name>.*)[\.\-_ ](?:dvdrip|bdrip|brrip|bluray|hdtv|divx|xvid|proper|repack|real\.proper|sub\.?fix|sub\.?pack|ac3d|unrated|1080i|1080p|720p|810p)',
                search_name, regex.I)
            if result:
                result = result.groupdict()

        if 'name' in result:
            name = regex.sub('\(.*?\)|\.|_', ' ', result['name'])
            if 'year' in result:
                year = result['year']
            else:
                year = ''
            return {'name': name, 'year': year}

    return None