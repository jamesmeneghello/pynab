import pytvmaze

from pynab import log
import pynab.ids


TVMAZE_SEARCH_URL = ' http://api.tvmaze.com/search/shows'


NAME = 'TVMAZE'


def search(data):
    """
    Search TVMaze for Show Info.

    :param release: release data
    :return: show details
    """
    year = data.get('year')
    country = data.get('country')
    clean_name = pynab.ids.clean_name(data.get('name'))

    log.debug('tvmaze: attempting to find "{}" online'.format(clean_name))

    # code contributed by srob650 (https://github.com/srob650)
    showname = ''

    if year:
        showname = clean_name[:-5]

    if country:
        showname = clean_name.split(country)[0].strip()

    if not year or country:
        showname = clean_name

    maze_show = None
    try:
        maze_show = pytvmaze.get_show(show_name=showname, show_year=year, show_country=country)
    except Exception:
        pass

    if maze_show:
        log.debug('tvmaze: returning show - {} with id - {}'.format(maze_show.name, maze_show.id))
        return maze_show.id
    else:
        log.debug('tvmaze: No show found')
        return None
