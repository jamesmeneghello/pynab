import regex
import unicodedata
import difflib
import datetime
import pymongo
import requests
import pytz

from pynab.db import db_session, Release, Movie, MetaBlack, Category, DataLog
from pynab import log
import config


OMDB_SEARCH_URL = 'http://www.omdbapi.com/?s='
OMDB_DETAIL_URL = 'http://www.omdbapi.com/?i='


def process(limit=100, online=True):
    """Process movies without imdb data and append said data."""
    expiry = datetime.datetime.now(pytz.utc) - datetime.timedelta(config.postprocess.get('fetch_blacklist_duration', 7))

    with db_session() as db:
        # clear expired metablacks
        db.query(MetaBlack).filter(MetaBlack.movie!=None).filter(MetaBlack.time <= expiry).delete(synchronize_session='fetch')

        query = db.query(Release).filter(Release.movie==None).join(Category).filter(Category.parent_id==2000)

        if online:
            query = query.filter(Release.movie_metablack_id==None)

        if limit:
            releases = query.order_by(Release.posted.desc()).limit(limit)
        else:
            releases = query.order_by(Release.posted.desc()).all()

        for release in releases:
            name, year = parse_movie(release.search_name)
            if name and year:
                method = 'local'
                imdb = db.query(Movie).filter(
                    Movie.name.ilike('%'.join(clean_name(name).split(' ')))
                ).filter(Movie.year==year).first()
                if not imdb and online:
                    method = 'online'
                    movie = search(clean_name(name), year)
                    if movie and movie['Type'] == 'movie':
                        imdb = db.query(Movie).filter(Movie.id==movie['imdbID']).first()
                        if not imdb:
                            imdb = Movie()
                            imdb.id = movie['imdbID']
                            imdb.name = movie['Title']
                            imdb.year = movie['Year']
                            db.add(imdb)
                if imdb:
                    log.info('imdb: [{}] - [{}] - movie data added: {}'.format(
                        release.id,
                        release.search_name,
                        method
                    ))
                    release.movie = imdb
                    release.movie_metablack_id = None
                    db.add(release)
                elif not imdb and online:
                    log.warning('imdb: [{}] - [{}] - movie data not found: online'.format(
                        release.id,
                        release.search_name
                    ))

                    mb = MetaBlack(status='ATTEMPTED', movie=release)
                    db.add(mb)
                else:
                    log.warning('imdb: [{}] - [{}] - movie data not found: local'.format(
                        release.id,
                        release.search_name
                    ))
            else:
                log.error('imdb: [{}] - [{}] - movie data not found: no suitable regex for movie name'.format(
                    release.id,
                    release.search_name
                ))
                db.add(MetaBlack(status='IMPOSSIBLE', movie=release))
                db.add(DataLog(description='imdb parse_movie regex', data=release.search_name))

        db.commit()


def search(name, year):
    """Search OMDB for a movie and return the IMDB ID."""

    # if we managed to parse the year from the name
    # include it, since it'll narrow results
    if year:
        year_query = '&y={}'.format(year.replace('(', '').replace(')', ''))
    else:
        year_query = ''

    r = requests.get(OMDB_SEARCH_URL + name + year_query)
    try:
        data = r.json()
    except:
        log.critical('There was a problem accessing the IMDB API page.')
        return None

    if 'Search' in data:
        for movie in data['Search']:
            # doublecheck, but the api should've searched properly
            ratio = difflib.SequenceMatcher(None, clean_name(name), clean_name(movie['Title'])).ratio()
            if ratio > 0.8 and year == movie['Year'] and movie['Type'] == 'movie':
                return movie


def get_details(id):
    r = requests.get(OMDB_DETAIL_URL + id)
    data = r.json()

    if 'Response' in data:
        imdb = {
            '_id': data['imdbID'],
            'title': data['Title'],
            'year': data['Year'],
            'genre': data['Genre'].split(',')
        }
        return imdb
    else:
        return None


def parse_movie(search_name):
    """Parses a movie name into name / year."""
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
            return name, year

    return None, None


def clean_name(name):
    """Cleans a show name for searching (against omdb)."""
    name = unicodedata.normalize('NFKD', name)
    name = regex.sub('[._\-]', ' ', name)
    name = regex.sub('[\':!"#*’,()?$&]', '', name)
    return name