import os
import sys
import pymongo
import gridfs
import datetime

sys.path.append(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))

import config
from pynab.db import engine, Base, db_session
import pynab.db
import pynab.util


def mongo_connect():
    return pymongo.MongoClient(config.mongo.get('host'), config.mongo.get('port'))[config.mongo.get('db')]


if __name__ == '__main__':
    print('Welcome to Pynab.')
    print('-----------------')
    print()
    print('Please ensure that you have copied and renamed config.sample.py to config.py before proceeding.')
    print()
    print('This script is destructive. Ensure that the database credentials and settings are correct.')
    print('The supplied database really should be empty, but it\'ll just drop anything it wants to overwrite.')
    print()
    input('To continue, press enter. To exit, press ctrl-c.')

    mongo = mongo_connect()
    fs = gridfs.GridFS(mongo)

    with db_session() as postgre:
        Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)

        from alembic.config import Config
        from alembic import command
        alembic_cfg = Config("alembic.ini")
        command.stamp(alembic_cfg, "head")

        print('Copying blacklists...')
        for blacklist in mongo.blacklists.find():
            blacklist.pop('_id')
            blacklist['status'] = bool(blacklist['status'])

            b = pynab.db.Blacklist(**blacklist)
            postgre.add(b)

        postgre.commit()

        print('Copying regexes...')
        custom_count = 100001
        for regex in mongo.regexes.find():
            if not str(regex['_id']).isdigit():
                # custom regex, add it to the end
                regex['id'] = custom_count
                custom_count += 1

            regex.pop('_id')
            regex.pop('category_id')
            regex['status'] = bool(regex['status'])

            r = pynab.db.Regex(**regex)
            postgre.add(r)

        postgre.commit()

        print('Updating regexes...')
        pynab.util.update_regex()

        print('Copying users...')
        for user in mongo.users.find():
            user.pop('_id')

            u = pynab.db.User(**user)
            postgre.add(u)

        postgre.commit()

        print('Copying TV shows...')
        for tvshow in mongo.tvrage.find():
            tvshow['id'] = str(tvshow['_id'])
            tvshow.pop('_id')

            tv = pynab.db.TvShow(**tvshow)
            postgre.add(tv)

        postgre.commit()

        print('Copying movies...')
        for movie in mongo.imdb.find():
            if movie['name'] and movie['year'] and 'tt' in str(movie['_id']):
                movie['id'] = str(movie['_id'])
                movie.pop('_id')

                if 'genre' in movie:
                    movie['genre'] = ','.join(movie['genre'])
                if 'lang' in movie:
                    movie.pop('lang')

                m = pynab.db.Movie(**movie)
                postgre.add(m)

        postgre.commit()

        print('Copying groups...')
        for group in mongo.groups.find():
            group.pop('_id')
            group['active'] = bool(group['active'])

            g = pynab.db.Group(**group)
            postgre.add(g)

        postgre.commit()

        print('Copying categories...')
        for category in mongo.categories.find():
            category['id'] = str(category['_id'])
            category.pop('_id')
            category.pop('min_size')
            category.pop('max_size')

            c = pynab.db.Category(**category)
            postgre.add(c)

        postgre.commit()

        print('Copying Releases, NZBs, NFOs and file data...')
        max_age = datetime.datetime.now() - datetime.timedelta(days=2045)
        active_groups = [g['_id'] for g in mongo.groups.find({'active': 1})]

        print(mongo.releases.find({'posted': {'$gte': max_age}, 'group._id': {'$in': active_groups}}).count())

        for release in mongo.releases.find({'posted': {'$gte': max_age}, 'group._id': {'$in': active_groups}}, timeout=False):
            # before even printing debug info, sanitise the names
            release['name'] = release['name'].encode('utf-8', 'replace').decode('latin-1')
            release['search_name'] = release['search_name'].encode('utf-8', 'replace').decode('latin-1')

            if postgre.query(pynab.db.Release).filter(pynab.db.Release.name==release['name']).filter(pynab.db.Release.posted==release['posted']).first():
                continue

            print('Processing {}...'.format(release['search_name'].encode('ascii', errors='ignore')))

            release.pop('_id')
            release.pop('id')
            c = postgre.query(pynab.db.Category).filter(pynab.db.Category.id==release['category']['_id']).first()
            release['category'] = c
            release.pop('completion')
            release.pop('file_count')

            # can't get file data because it's not informative enough
            # no biggie, we can re-process it
            if 'files' in release:
                release.pop('files')

            g = postgre.query(pynab.db.Group).filter(pynab.db.Group.name == release['group']['name']).first()
            release['group'] = g

            if 'regex' in release:
                if release['regex']:
                    r = postgre.query(pynab.db.Regex).filter(pynab.db.Regex.regex == release['regex']['regex']).first()
                    release['regex'] = r
                else:
                    release.pop('regex')

            if 'imdb' in release and release['imdb'] and '_id' in release['imdb'] and 'tt' in str(release['imdb']):
                release['movie'] = postgre.query(pynab.db.Movie).filter(pynab.db.Movie.id==str(release['imdb']['_id'])).first()
            if 'imdb' in release:
                release.pop('imdb')

            if release['nfo']:
                data = fs.get(release['nfo']).read()
                n = pynab.db.NFO(data=data)
                release['nfo'] = n
            else:
                release.pop('nfo')

            if release['nzb']:
                try:
                    data = fs.get(release['nzb']).read()
                except:
                    continue
                n = pynab.db.NZB(data=data)
                release['nzb'] = n
            else:
                release.pop('nzb')

            release.pop('size')
            release.pop('spotnab_id')
            release.pop('total_parts')

            if 'tvdb' in release:
                release.pop('tvdb')

            if 'tvrage' in release:
                if release['tvrage']:
                    if '_id' in release['tvrage']:
                        t = postgre.query(pynab.db.TvShow).filter(pynab.db.TvShow.id==release['tvrage']['_id']).first()
                        release['tvshow'] = t
                        if release['tv']:
                            e = postgre.query(pynab.db.Episode)\
                                .filter(pynab.db.Episode.tvshow_id==release['tvshow'].id)\
                                .filter(pynab.db.Episode.series_full==release['tv']['series_full']).first()
                            if not e:
                                release['tv'].pop('name')
                                release['tv'].pop('clean_name')
                                if 'country' in release['tv']:
                                    release['tvshow'].country = release['tv']['country']
                                    release['tv'].pop('country')
                                else:
                                    release['tvshow'].country = 'US'
                                e = pynab.db.Episode(**release['tv'])
                                e.tvshow_id = release['tvshow'].id

                            release['episode'] = e
                release.pop('tvrage')

            if 'tv' in release:
                release.pop('tv')

            if 'updated' in release:
                release.pop('updated')
            release.pop('nzb_size')

            if 'passworded' in release:
                if release['passworded'] is False:
                    release['passworded'] = 'NO'
                if release['passworded'] is True:
                    release['passworded'] = 'YES'
                if release['passworded'] == 'potentially':
                    release['passworded'] = 'MAYBE'
                if release['passworded'] == 'unknown':
                    release['passworded'] = 'UNKNOWN'

            if 'unwanted' in release:
                release.pop('unwanted')

            if 'req_id' in release:
                release.pop('req_id')

            r = pynab.db.Release(**release)
            postgre.add(r)
            try:
                postgre.flush()
            except:
                # ignore duplicates
                pass

