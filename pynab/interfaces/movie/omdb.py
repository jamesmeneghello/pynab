import requests
import difflib

from pynab import log
import pynab.ids


OMDB_SEARCH_URL = 'http://www.omdbapi.com/?s='


NAME = 'OMDB'


def search(data):
    """
    Search OMDB for an id based on a name/year.

    :param data: {name, year}
    :return: id
    """

    name = data['name']
    year = data['year']

    # if we managed to parse the year from the name
    # include it, since it'll narrow results
    if year:
        year_query = '&y={}'.format(year.replace('(', '').replace(')', ''))
    else:
        year_query = ''

    try:
        result = requests.get(OMDB_SEARCH_URL + name + year_query).json()
    except:
        log.critical('There was a problem accessing the IMDB API page.')
        return None

    if 'Search' in result:
        for movie in result['Search']:
            # doublecheck, but the api should've searched properly
            ratio = difflib.SequenceMatcher(None, pynab.ids.clean_name(name), pynab.ids.clean_name(movie['Title'])).ratio()
            if ratio > 0.8 and year == movie['Year'] and movie['Type'] == 'movie':
                return movie['imdbID']

    return None

