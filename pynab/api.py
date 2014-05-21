import datetime
import os
import gzip

from mako.template import Template
from mako import exceptions
from bottle import request, response
from sqlalchemy.orm import aliased
from sqlalchemy import or_

from pynab.db import db_session, NZB, NFO, Release, User, Category, Movie, TvShow, Group, Episode, File
from pynab import log, root_dir
import config


RESULT_TEMPLATE = Template(filename=os.path.join(root_dir, 'templates/api/result.mako'))


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
        id = request.query.guid or None
        if id:
            with db_session() as db:
                release = db.query(Release).join(NFO).filter(Release.id==id).one()
                if release:
                    data = release.nfo.data
                    response.set_header('Content-type', 'application/x-nfo')
                    response.set_header('Content-Disposition', 'attachment; filename="{0}"'
                        .format(release.search_name.replace(' ', '_') + '.nfo')
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
        id = request.query.guid or None
        if not id:
            id = request.query.id or None

        if id:
            with db_session() as db:
                release = db.query(Release).join(NZB).join(Category).filter(Release.id==id).one()
                if release:
                    release.grabs += 1
                    db.merge(release)
                    db.commit()

                    data = release.nzb.data
                    response.set_header('Content-type', 'application/x-nzb')
                    response.set_header('X-DNZB-Name', release.search_name)
                    response.set_header('X-DNZB-Category', release.category.name)
                    response.set_header('Content-Disposition', 'attachment; filename="{0}"'
                        .format(release.search_name.replace(' ', '_') + '.nzb')
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

    with db_session() as db:
        user = db.query(User).filter(User.api_key==api_key).one()
        if user:
            return api_key
        else:
            return False


def movie_search(dataset=None):
    if auth():
        with db_session() as db:
            query = db.query(Release)

            try:
                imdb_id = request.query.imdbid or None
                if imdb_id:
                    query = query.join(Movie).filter(Movie.id=='tt'+imdb_id)

                genres = request.query.genre or None
                if genres:
                    query = query.join(Movie)
                    for genre in genres.split(','):
                        query = query.filter(or_(Movie.genre.ilike('%{}%'.format(genre))))
            except:
                return api_error(201)

            return search(dataset, query)
    else:
        return api_error(100)


def tv_search(dataset=None):
    if auth():
        with db_session() as db:
            query = db.query(Release)

            try:
                tvrage_id = request.query.rid or None
                if tvrage_id:
                    query = query.join(TvShow).filter(TvShow.id==int(tvrage_id))

                season = request.query.season or None
                if season:
                    if season.isdigit():
                        query = query.join(Episode).filter(Episode.season=='S{:02d}'.format(int(season)))
                    else:
                        query = query.join(Episode).filter(Episode.season==season)

                episode = request.query.ep or None
                if episode:
                    if episode.isdigit():
                        query = query.join(Episode).filter(Episode.episode=='E{:02d}'.format(int(episode)))
                    else:
                        query = query.join(Episode).filter(Episode.episode==episode)
            except:
                return api_error(201)

            return search(dataset, query)
    else:
        return api_error(100)


def details(dataset=None):
    if auth():
        if request.query.id:
            with db_session() as db:
                release = db.query(Release).filter(Release.id==request.query.id).one()
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
    if not dataset:
        dataset = {}

    dataset['app_version'] = config.api.get('version', '1.0.0')
    dataset['api_version'] = config.api.get('api_version', '0.2.3')
    dataset['email'] = config.api.get('email', '')
    dataset['result_limit'] = config.api.get('result_limit', 20)
    dataset['result_default'] = config.api.get('result_default', 20)

    with db_session() as db:
        category_alias = aliased(Category)
        dataset['categories'] = db.query(Category).filter(Category.parent_id==None).join(category_alias, Category.children).all()

        totals = []

        totals += [
            {
                'label': 'TV',
                'total': db.query(Release.id).join(Category).filter(Category.parent_id==5000).group_by(Release.id).count(),
                'processed': db.query(Release.id).join(Category).join(TvShow).filter(Category.parent_id==5000).group_by(Release.id).count()
            },
            {
                'label': 'Movies',
                'total': db.query(Release.id).join(Category).filter(Category.parent_id==2000).group_by(Release.id).count(),
                'processed': db.query(Release.id).join(Category).join(Movie).filter(Category.parent_id==2000).group_by(Release.id).count()
            },
            {
                'label': 'NFOs',
                'total': db.query(Release.id).join(Category).group_by(Release.id).count(),
                'processed': db.query(Release.id).join(Category).join(NFO).group_by(Release.id).count()
            },
            {
                'label': 'Files',
                'total': db.query(Release.id).join(Category).group_by(Release.id).count(),
                'processed': db.query(Release.id).join(Category).join(File).filter(Release.files.any()).group_by(Release.id).count()
            }
        ]


        try:
            tmpl = Template(
                filename=os.path.join(root_dir, 'templates/api/caps.mako'))
            return tmpl.render(**dataset)
        except:
            log.error('Failed to deliver page: {0}'.format(exceptions.text_error_template().render()))
            return None


def search(dataset=None, query=None):
    if auth():
        # build the mongo query
        # add params if coming from a tv-search or something
        with db_session() as db:
            if not query:
                query = db.query(Release)

            try:
                # get categories
                cat_ids = request.query.cat or []
                if cat_ids:
                    query = query.join(Category)
                    cat_ids = cat_ids.split(',')
                    query = query.filter(Category.id.in_(cat_ids))

                # group names
                group_names = request.query.group or []
                if group_names:
                    query = query.join(Group)
                    group_names = group_names.split(',')
                    for group in group_names:
                        query = query.filter(Group.name==group)

                # max age
                max_age = request.query.maxage or None
                if max_age:
                    oldest = datetime.datetime.now() - datetime.timedelta(int(max_age))
                    query = query.filter(Release.posted>oldest)

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

            except Exception as e:
                # normally a try block this long would make me shudder
                # but we don't distinguish between errors, so it's fine
                log.error('Incorrect API Parameter or parsing error: {}'.format(e))
                return api_error(201)

            search_terms = request.query.q or None
            if search_terms:
                # we're searching specifically for a show or something
                if search_terms:
                    for term in search_terms.split(' '):
                        query = query.filter(Release.search_name.ilike('%{}%'.format(term)))

            query = query.order_by(Release.posted.desc())

            query = query.limit(limit)
            query = query.offset(offset)

            total = query.count()
            results = query.all()

            dataset['releases'] = results
            dataset['offset'] = offset
            dataset['total'] = total
            dataset['api_key'] = request.query.apikey

            try:
                return RESULT_TEMPLATE.render(**dataset)
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
