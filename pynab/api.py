import datetime
import os
import gzip

from mako.template import Template
from mako import exceptions
from bottle import request, response
from sqlalchemy.orm import aliased
from sqlalchemy import or_, func, desc

from pynab.db import db_session, NZB, NFO, Release, User, Category, Movie, TvShow, Group, Episode
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
                release = db.query(Release).join(NFO).filter(Release.id == id).one()
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
    user = auth()
    if user:
        id = request.query.guid or None
        if not id:
            id = request.query.id or None

        # couchpotato doesn't support nzb.gzs, so decompress them
        decompress = 'CouchPotato' in request.headers.get('User-Agent')

        if id:
            with db_session() as db:
                release = db.query(Release).join(NZB).join(Category).filter(Release.id == id).one()
                if release:
                    release.grabs += 1
                    user.grabs += 1
                    db.merge(release)
                    db.merge(user)
                    db.commit()

                    if decompress:
                        data = release.nzb.data
                        response.set_header('Content-type', 'application/x-nzb')
                        response.set_header('X-DNZB-Name', release.search_name)
                        response.set_header('X-DNZB-Category', release.category.name)
                        response.set_header('Content-Disposition', 'attachment; filename="{0}"'
                                            .format(release.search_name.replace(' ', '_') + '.nzb')
                        )
                        return gzip.decompress(data)
                    else:
                        data = release.nzb.data
                        response.set_header('Content-type', 'application/x-nzb-compressed-gzip')
                        response.set_header('X-DNZB-Name', release.search_name)
                        response.set_header('X-DNZB-Category', release.category.name)
                        response.set_header('Content-Disposition', 'attachment; filename="{0}"'
                                            .format(release.search_name.replace(' ', '_') + '.nzb.gz')
                        )
                        return data
                else:
                    return api_error(300)
        else:
            return api_error(200)
    else:
        return api_error(100)


def auth():
    api_key = request.query.apikey or ''

    with db_session() as db:
        user = db.query(User).filter(User.api_key == api_key).first()
        if user:
            return user
        else:
            return False


def movie_search(dataset=None):
    if auth():
        with db_session() as db:
            query = db.query(Release)

            try:
                imdb_id = request.query.imdbid or None
                if imdb_id:
                    query = query.join(Movie).filter(Movie.id == 'tt' + imdb_id)

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
                    query = query.join(TvShow).filter(TvShow.id == int(tvrage_id))

                season = request.query.season or None
                episode = request.query.ep or None

                if season or episode:
                    release_alias = aliased(Release)
                    query = query.join(Episode, release_alias)

                    if season:
                        # 2014, do nothing
                        if season.isdigit() and len(season) <= 2:
                            # 2, convert to S02
                            season = 'S{:02d}'.format(int(season))

                        query = query.filter(Episode.season == season)

                    if episode:
                        # 23/10, do nothing
                        if episode.isdigit() and '/' not in episode:
                            # 15, convert to E15
                            episode = 'E{:02d}'.format(int(episode))

                        query = query.filter(Episode.episode == episode)
            except Exception as e:
                log.error('API Error: {}'.format(e))
                return api_error(201)

            return search(dataset, query)
    else:
        return api_error(100)


def details(dataset=None):
    if auth():
        if request.query.id:
            with db_session() as db:
                release = db.query(Release).filter(Release.id == request.query.id).one()
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
        dataset['categories'] = db.query(Category).filter(Category.parent_id == None).join(category_alias,
                                                                                           Category.children).all()
        try:
            tmpl = Template(
                filename=os.path.join(root_dir, 'templates/api/caps.mako'))
            return tmpl.render(**dataset)
        except:
            log.error('Failed to deliver page: {0}'.format(exceptions.text_error_template().render()))
            return None


def stats(dataset=None):
    if not dataset:
        dataset = {}

    with db_session() as db:
        tv_totals = db.query(func.count(Release.tvshow_id), func.count(Release.tvshow_metablack_id),
                             func.count(Release.id)).join(Category).filter(Category.parent_id == 5000).one()
        movie_totals = db.query(func.count(Release.movie_id), func.count(Release.movie_metablack_id),
                                func.count(Release.id)).join(Category).filter(Category.parent_id == 2000).one()
        nfo_total = db.query(func.count(Release.nfo_id), func.count(Release.nfo_metablack_id)).one()
        file_total = db.query(Release.id).filter((Release.files.any()) | (Release.passworded != 'UNKNOWN')).count()
        file_failed_total = db.query(func.count(Release.rar_metablack_id)).one()
        release_total = db.query(Release.id).count()

        dataset['totals'] = {
            'TV': {
                'processed': tv_totals[0],
                'failed': tv_totals[1],
                'total': tv_totals[2]
            },
            'Movies': {
                'processed': movie_totals[0],
                'failed': movie_totals[1],
                'total': movie_totals[2]
            },
            'NFOs': {
                'processed': nfo_total[0],
                'failed': nfo_total[1],
                'total': release_total
            },
            'File Info': {
                'processed': file_total,
                'failed': file_failed_total[0],
                'total': release_total
            }
        }

        dataset['categories'] = db.query(Category, func.count(Release.id)).join(Release).group_by(Category).order_by(
            desc(func.count(Release.id))).all()

        dataset['groups'] = db.query(Group, func.min(Release.posted), func.count(Release.id)).join(Release).group_by(Group).order_by(desc(func.count(Release.id))).all()

        try:
            tmpl = Template(
                filename=os.path.join(root_dir, 'templates/api/stats.mako'))
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
                    query = query.filter(Category.id.in_(cat_ids) | Category.parent_id.in_(cat_ids))

                # group names
                group_names = request.query.group or []
                if group_names:
                    query = query.join(Group)
                    group_names = group_names.split(',')
                    for group in group_names:
                        query = query.filter(Group.name == group)

                # max age
                max_age = request.query.maxage or None
                if max_age:
                    oldest = datetime.datetime.now() - datetime.timedelta(int(max_age))
                    query = query.filter(Release.posted > oldest)

                # more info?
                extended = request.query.extended or None
                if extended:
                    dataset['extended'] = True
                else:
                    dataset['extended'] = False

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

            if config.api.get('postprocessed_only', False):
                query = query.filter(Release.passworded!='UNKNOWN')

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
    'stats': stats,
}
