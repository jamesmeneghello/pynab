import datetime
import os
import gzip
import pymongo
import pprint

from mako.template import Template
from mako import exceptions
from bottle import request, response

from pynab.db import db, fs
from pynab import log, root_dir
import config


def api_error(code):
    xml_header = '<?xml version="1.0" encoding="UTF-8"?>'

    errors = {
        100: 'Incorrect user credentials',
        101: 'Account suspended',
        102: 'Insufficient privileges/not authorized',
        103: 'Registration denied',
        104: 'Registrations are closed',
        105: 'Invalid registration (Email Address Taken)',
        106: 'Invalid registration (Email Address Bad Format)',
        107: 'Registration Failed (Data error)',
        200: 'Missing parameter',
        201: 'Incorrect parameter',
        202: 'No such function. (Function not defined in this specification).',
        203: 'Function not available. (Optional function is not implemented).',
        300: 'No such item.',
        301: 'Item already exists.',
        900: 'Unknown error',
        910: 'API Disabled',
    }

    if code in errors:
        error = errors[code]
    else:
        error = 'Something really, really bad happened.'

    return '{0}\n<error code=\"{1:d}\" description=\"{2}\" />'.format(xml_header, code, error)


def get_nfo(dataset=None):
    if auth():
        guid = request.query.guid or None
        if guid:
            release = db.releases.find_one({'id': guid})
            if release:
                data = fs.get(release['nfo']).read()
                response.set_header('Content-type', 'application/x-nfo')
                response.set_header('Content-Disposition', 'attachment; filename="{0}"'
                .format(release['search_name'].replace(' ', '_') + '.nfo')
                )
                return gzip.decompress(data)
            else:
                return api_error(300)
        else:
            return api_error(200)
    else:
        return api_error(100)


def get_nzb(dataset=None):
    if auth():
        guid = request.query.guid or None
        if not guid:
            guid = request.query.id or None

        if guid:
            release = db.releases.find_one({'id': guid})
            if release:
                data = fs.get(release['nzb']).read()
                response.set_header('Content-type', 'application/x-nzb')
                response.set_header('X-DNZB-Name', release['search_name'])
                response.set_header('X-DNZB-Category', release['category']['name'])
                response.set_header('Content-Disposition', 'attachment; filename="{0}"'
                .format(release['search_name'].replace(' ', '_') + '.nzb')
                )
                return gzip.decompress(data)
            else:
                return api_error(300)
        else:
            return api_error(200)
    else:
        return api_error(100)


def auth():
    api_key = request.query.apikey or ''

    user = db.users.find_one({'api_key': api_key})
    if user:
        return api_key
    else:
        return False


def movie_search(dataset=None):
    if auth():
        query = dict()
        query['category._id'] = {'$in': [2020, 2030, 2040, 2050, 2060]}

        try:
            imdb_id = request.query.imdbid or None
            if imdb_id:
                query['imdb._id'] = 'tt' + imdb_id

            genres = request.query.genre or None
            if genres:
                genres = genres.split(',')
                query['imdb.genre'] = {'$in': genres}
        except:
            return api_error(201)

        return search(dataset, query)
    else:
        return api_error(100)


def tv_search(dataset=None):
    if auth():
        query = dict()
        query['category._id'] = {'$in': [5030, 5040, 5050, 5060, 5070, 5080]}

        try:
            tvrage_id = request.query.rid or None
            if tvrage_id:
                query['tvrage._id'] = int(tvrage_id)

            season = request.query.season or None
            if season:
                if season.isdigit():
                    query['tv.season'] = 'S{:02d}'.format(int(season))
                else:
                    query['tv.season'] = season

            episode = request.query.ep or None
            if episode:
                if episode.isdigit():
                    query['tv.episode'] = 'E{:02d}'.format(int(episode))
                else:
                    query['tv.episode'] = episode
        except:
            return api_error(201)

        return search(dataset, query)
    else:
        return api_error(100)


def details(dataset=None):
    if auth():
        if request.query.id:
            release = db.releases.find_one({'id': request.query.id})
            if release:
                dataset['releases'] = [release]
                dataset['detail'] = True
                dataset['api_key'] = request.query.apikey

                try:
                    tmpl = Template(
                        filename=os.path.join(root_dir, 'templates/api/result.mako'))
                    return tmpl.render(**dataset)
                except:
                    log.error('Failed to deliver page: {0}'.format(exceptions.text_error_template().render()))
                    return None
            else:
                return api_error(300)
        else:
            return api_error(200)
    else:
        return api_error(100)


def caps(dataset=None):
    dataset['app_version'] = config.api.get('version', '1.0.0')
    dataset['api_version'] = config.api.get('api_version', '0.2.3')
    dataset['email'] = config.api.get('email', '')
    dataset['result_limit'] = config.api.get('result_limit', 20)
    dataset['result_default'] = config.api.get('result_default', 20)

    categories = {}
    for category in db.categories.find():
        if category.get('parent_id'):
            categories[category.get('parent_id')]['categories'].append(category)
        else:
            categories[category.get('_id')] = category
            categories[category.get('_id')]['categories'] = []
    dataset['categories'] = categories

    try:
        tmpl = Template(
            filename=os.path.join(root_dir, 'templates/api/caps.mako'))
        return tmpl.render(**dataset)
    except:
        log.error('Failed to deliver page: {0}'.format(exceptions.text_error_template().render()))
        return None


def search(dataset=None, params=None):
    if auth():
        # build the mongo query
        # add params if coming from a tv-search or something
        if params:
            query = dict(params)
        else:
            query = dict()

        try:
            # set limit to request or default
            # this will also match limit == 0, which would be infinite
            limit = request.query.limit or None
            if limit and int(limit) <= int(config.api.get('result_limit', 100)):
                limit = int(limit)
            else:
                limit = int(config.api.get('result_default', 20))

            # offset is only available for rss searches and won't work with text
            offset = request.query.offset or None
            if offset and int(offset) > 0:
                offset = int(offset)
            else:
                offset = 0

            # get categories
            cat_ids = request.query.cat or []
            if cat_ids:
                cat_ids = [int(c) for c in cat_ids.split(',')]
                categories = []
                for category in db.categories.find({'_id': {'$in': cat_ids}}):
                    if 'parent_id' not in category:
                        for child in db.categories.find({'parent_id': category['_id']}):
                            categories.append(child['_id'])
                    else:
                        categories.append(category['_id'])
                if 'category._id' in query:
                    query['category._id'].update({'$in': categories})
                else:
                    query['category._id'] = {'$in': categories}

            # group names
            grp_names = request.query.group or []
            if grp_names:
                grp_names = grp_names.split(',')
                groups = [g['_id'] for g in db.groups.find({'name': {'$in': grp_names}})]
                query['group._id'] = {'$in': groups}

            # max age
            max_age = request.query.maxage or None
            if max_age:
                oldest = datetime.datetime.now() - datetime.timedelta(int(max_age))
                query['posted'] = {'$gte': oldest}
        except Exception as e:
            # normally a try block this long would make me shudder
            # but we don't distinguish between errors, so it's fine
            log.error('Incorrect API Paramter or parsing error: {}'.format(e))
            return api_error(201)

        log.debug('Query parameters: {0}'.format(query))

        search_terms = request.query.q or None
        if search_terms:
            # we're searching specifically for a show or something

            # mash search terms into a single string
            # we remove carets because mongo's FT search is probably smart enough
            terms = ''
            if search_terms:
                terms = ' '.join(['\"{}\"'.format(term) for term in search_terms.replace('^', '').split(' ')])

            # build the full query - db.command() uses a different format
            full = {
                'command': 'text',
                'value': 'releases',
                'search': terms,
                'filter': query,
                'limit': limit,
            }

            results = db.command(**full)['results']

            if results:
                results = [r['obj'] for r in results]
            else:
                results = []

            # since FT searches don't support offsets
            total = limit
            offset = 0
        else:
            # we're looking for an rss feed
            # return results and sort by postdate ascending
            total = db.releases.find(query).count()
            results = db.releases.find(query, limit=int(limit), skip=int(offset)).sort('posted', pymongo.DESCENDING)

        dataset['releases'] = results
        dataset['offset'] = offset
        dataset['total'] = total
        dataset['search'] = True
        dataset['api_key'] = request.query.apikey

        pprint.pprint(results)

        try:
            tmpl = Template(
                filename=os.path.join(root_dir, 'templates/api/result.mako'))
            return tmpl.render(**dataset)
        except:
            log.error('Failed to deliver page: {0}'.format(exceptions.text_error_template().render()))
            return None
    else:
        return api_error(100)


functions = {
    's|search': search,
    'c|caps': caps,
    'd|details': details,
    'tv|tvsearch': tv_search,
    'm|movie': movie_search,
    'g|get': get_nzb,
    'gn|getnfo': get_nfo,
}
