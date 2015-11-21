import unicodedata
import datetime
import time

import regex
import roman
import pytz

from pynab.db import db_session, Release, Category, TvShow, MetaBlack, Episode, DataLog, windowed_query, DBID
import pytvmaze
from pynab import log
import pynab.util
import config


PROCESS_CHUNK_SIZE = 500

TVMAZE_SEARCH_URL = ' http://api.tvmaze.com/search/shows'


def process(limit=None, online=True):
    """Processes [limit] releases to add TVMaze information."""
    expiry = datetime.datetime.now(pytz.utc) - datetime.timedelta(config.postprocess.get('fetch_blacklist_duration', 7))

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
                    maze = release.tvshow
                else:
                    maze = db.query(TvShow).filter(TvShow.name.ilike('%'.join(show['clean_name'].split(' ')))).first()

                if not maze and 'and' in show['clean_name']:
                    maze = db.query(TvShow).filter(TvShow.name == show['clean_name'].replace(' and ', ' & ')).first()

                #Check if its REALLY in the db
                if maze:
                    tvmaze = db.query(DBID).filter(DBID.tvshow_id == maze.id).filter(DBID.db == 'TVMAZE').first()
                else:
                    tvmaze = None

                if maze and tvmaze:
                    method = 'local'
                elif not maze and online:
                    try:
                        maze_data = search(show)
                    except Exception as e:
                        log.error('tvmaze: either the show wasn\'t found or tvmaze is down')
                        continue

                    if maze_data:
                        method = 'online'
                        tvmaze = db.query(DBID).filter(DBID.db_id == str(maze_data.id)).filter(DBID.db == 'TVMAZE').first()

                        if tvmaze:
                            maze = db.query(TvShow).filter(TvShow.id == tvmaze.tvshow_id).first()
                        else:
                            try:
                                country = maze_data.network['country']['code']
                            except Exception as e:
                                country = None
                                log.info('tvmaze: No country found for - {}'.format(maze_data.name))

                            if country:
                                maze = TvShow(name=maze_data.name, country=country)
                            else:
                                maze = TvShow(name=maze_data.name)
                            db.add(maze)

                            dbid = DBID(db='TVMAZE', db_id=maze_data.id, tvshow_id=maze.id)
                            db.add(dbid)

                    # wait slightly so we don't smash the api
                    time.sleep(1)

                if maze:
                    log.info('tvmaze: add {} [{}]'.format(
                        method,
                        release.search_name
                    ))
                    #######
                    e = db.query(Episode).filter(Episode.tvshow_id == maze.id).filter(Episode.series_full == show['series_full']).first()

                    if not e:
                        e = Episode(
                            season=show.get('season'),
                            episode=show.get('episode'),
                            series_full=show.get('series_full'),
                            air_date=show.get('air_date'),
                            year=show.get('year'),
                            tvshow_id=maze.id
                        )
                    release.tvshow = maze
                    release.tvshow_metablack_id = None
                    release.episode = e
                    db.add(release)
                elif not maze and online:
                    log.debug('tvmaze: [{}] - tvmaze failed: {}'.format(
                        release.search_name,
                        'no show found (online)'
                    ))

                    mb = MetaBlack(tvshow=release, status='ATTEMPTED')
                    db.add(mb)
                else:
                    log.debug('tvmaze: [{}] - tvmaze failed: {}'.format(
                        release.search_name,
                        'no show found (local)'
                    ))
            else:
                log.debug('tvmaze: [{}] - tvmaze failed: {}'.format(
                    release.search_name,
                    'no suitable regex for show name'
                ))
                db.add(MetaBlack(tvshow=release, status='IMPOSSIBLE'))
                db.add(DataLog(description='tvmaze parse_show regex', data=release.search_name))

            db.commit()


def search(show):
    """Searches tvmaze for show details"""
    year = show.get('year')
    country = show.get('country')

    log.info('tvmaze: attempting to find {} online'.format(show['clean_name']))

    #Code contributed by srob650 (https://github.com/srob650)
    if year:
        showname = show['clean_name'][:-5]

    if country:
        showname = show['clean_name'].split(country)[0].strip()

    if not year or country:
        showname = show['clean_name']

    maze_show = pytvmaze.get_show(show_name=showname, show_year=year, show_country=country)

    if maze_show is not None:
        log.info('tvmaze: returning show - {} with id - {}'.format(maze_show.name, maze_show.id))
        return maze_show
    else:
        log.info('tvmaze: No show found')
        return None


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