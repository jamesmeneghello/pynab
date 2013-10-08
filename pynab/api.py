import datetime
import os
import pymongo

from mako.template import Template
from mako import exceptions
from bottle import request
from pynab.db import db
from pynab import log
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


def auth():
    api_key = request.query.apikey or ''

    user = db.users.find_one({'api_key': api_key})
    if user:
        return True
    else:
        return False


def details():
    dataset = dict()

    if request.query.id:
        release = db.releases.find_one({'id': request.query.id})
        if release:
            dataset['releases'] = [release]
            dataset['detail'] = True

            try:
                tmpl = Template(
                    filename=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..',
                                          'templates/api/result.mako'))
                return tmpl.render(**dataset)
            except:
                log.error('Failed to deliver page: {0}'.format(exceptions.text_error_template().render()))
                return None
        else:
            api_error(300)
    else:
        api_error(200)


def caps():
    dataset = dict()

    dataset['app_version'] = config.site['version']
    dataset['api_version'] = config.site['api_version']
    dataset['email'] = config.site['email'] or ''
    dataset['result_limit'] = config.site['result_limit'] or 20
    dataset['result_default'] = config.site['result_default'] or 20

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
            filename=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'templates/api/caps.mako'))
        return tmpl.render(**dataset)
    except:
        log.error('Failed to deliver page: {0}'.format(exceptions.text_error_template().render()))
        return None


def search(params=None):
    # build the mongo query
    if params:
        query = dict(params)
    else:
        query = dict()

    try:
        # set limit to request or default
        # this will also match limit == 0, which would be infinite
        limit = request.query.limit or None
        if not limit or limit > int(config.site['result_limit']):
            limit = int(config.site['result_default'])

        # offset is only available for rss searches and won't work with text
        offset = request.query.offset or None
        if not offset or int(offset) < 0:
            offset = 0

        # get categories
        cat_ids = request.query.cat or []
        if cat_ids:
            cat_ids = [int(c) for c in cat_ids.split(',')]
            categories = []
            for category in db.categories.find({'id': {'$in': cat_ids}}):
                if 'parent_id' not in category:
                    for child in db.categories.find({'parent_id': category['_id']}):
                        categories.append(child['_id'])
                else:
                    categories.append(category['_id'])
            query['category_id'] = {'$in': categories}

        # group names
        grp_names = request.query.group or []
        if grp_names:
            grp_names = grp_names.split(',')
            groups = [g['_id'] for g in db.groups.find({'name': {'$in': grp_names}})]
            query['group_id'] = {'$in': groups}

        # max age
        max_age = request.query.maxage or None
        if max_age:
            oldest = datetime.datetime.now() - datetime.timedelta(int(max_age))
            query['posted'] = {'$gte': oldest}
    except:
        # normally a try block this long would make me shudder
        # but we don't distinguish between errors, so it's fine
        return api_error(201)

    search_terms = request.query.query or None
    if search_terms:
        # we're searching specifically for a show or something

        # mash search terms into a single string
        # we remove carets because mongo's FT search is probably smart enough
        terms = ''
        if search_terms:
            terms = '{0}'.format(' '.join(search_terms.replace('^', ' ').split(' '))).strip()

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
        results = db.releases.find(query, limit=int(limit), skip=int(offset)).sort('posted', pymongo.ASCENDING)

    dataset = dict()
    dataset['releases'] = results
    dataset['offset'] = offset
    dataset['total'] = total
    dataset['search'] = True

    try:
        tmpl = Template(
            filename=os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'templates/api/result.mako'))
        return tmpl.render(**dataset)
    except:
        log.error('Failed to deliver page: {0}'.format(exceptions.text_error_template().render()))
        return None


functions = {
    's|search': search,
    'c|caps': caps,
    'd|details': details,
}
"""

'g|get': get_data,
'gn|getnfo': get_nfo,


'tv|tvsearch': tv_search,
'm|movie': movie_search,
'b|book': book_search
"""