import regex
import unicodedata
import difflib
import datetime
import pymongo
import requests
import pytz

from pynab.db import db
from pynab import log
import config


OMDB_SEARCH_URL = 'http://www.omdbapi.com/?s='
OMDB_DETAIL_URL = 'http://www.omdbapi.com/?i='


def process_release(release, online=True):
    name, year = parse_movie(release['search_name'])
    if name and year:
        method = 'local'
        imdb = db.imdb.find_one({'name': clean_name(name), 'year': year})
        if not imdb and online:
            method = 'online'
            movie = search(clean_name(name), year)
            if movie and movie['Type'] == 'movie':
                db.imdb.update(
                    {'_id': movie['imdbID']},
                    {
                        '$set': {
                            'name': movie['Title'],
                            'year': movie['Year']
                        }
                    },
                    upsert=True
                )
                imdb = db.imdb.find_one({'_id': movie['imdbID']})

        if imdb:
            log.info('[{}] - [{}] - imdb added: {}'.format(
                release['_id'],
                release['search_name'],
                method
            ))
            db.releases.update({'_id': release['_id']}, {
                '$set': {
                    'imdb': imdb
                }
            })
        elif not imdb and online:
            log.warning('[{}] - [{}] - imdb not found: online'.format(
                release['_id'],
                release['search_name']
            ))
            db.releases.update({'_id': release['_id']}, {
                '$set': {
                    'imdb': {
                        'attempted': datetime.datetime.now(pytz.utc)
                    }
                }
            })
        else:
            log.warning('[{}] - [{}] - imdb not found: local'.format(
                release['_id'],
                release['search_name']
            ))
    else:
        log.error('[{}] - [{}] - imdb not found: no suitable regex for movie name'.format(
            release['_id'],
            release['search_name']
        ))
        db.releases.update({'_id': release['_id']}, {
            '$set': {
                'imdb': {
                    'possible': False
                }
            }
        })


def process(limit=100, online=True):
    """Process movies without imdb data and append said data."""
    expiry = datetime.datetime.now(pytz.utc) - datetime.timedelta(config.postprocess.get('fetch_blacklist_duration', 7))

    query = {
        'imdb._id': {'$exists': False},
        'category.parent_id': 2000,
    }

    if online:
        query.update({
            'imdb.possible': {'$exists': False},
            '$or': [
                {'imdb.attempted': {'$exists': False}},
                {'imdb.attempted': {'$lte': expiry}}
            ]
        })
    for release in db.releases.find(query).limit(limit).sort('posted', pymongo.DESCENDING).batch_size(50):
        process_release(release, online)


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