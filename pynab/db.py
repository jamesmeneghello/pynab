import pymongo
import gridfs
import config


class DB:
    def __init__(self):
        self.mongo = None
        self.gridfs = None
        self.config = config.db
        self.connect()

    def connect(self):
        self.mongo = pymongo.MongoClient(self.config['host'], self.config['port'])
        self.create_indexes()

    def db(self):
        return self.mongo[self.config['db']]

    def fs(self):
        return gridfs.GridFS(self.mongo[self.config['db']])

    def create_indexes(self):
        # rather than scatter index creation everywhere, centralise it so it only runs once

        # categories
        self.db().categories.ensure_index('name', pymongo.ASCENDING)
        self.db().categories.ensure_index('parent_id', pymongo.ASCENDING)

        # regexes
        self.db().regexes.ensure_index('group_name', pymongo.ASCENDING)
        self.db().regexes.ensure_index('category_id', pymongo.ASCENDING)

        # groups
        self.db().groups.ensure_index('name', pymongo.ASCENDING)

        # users
        self.db().users.ensure_index('username', pymongo.ASCENDING)
        self.db().users.ensure_index('email', pymongo.ASCENDING)
        self.db().users.ensure_index('rsstoken', pymongo.ASCENDING)

        # tvrage
        self.db().tvrage.ensure_index('id', pymongo.ASCENDING)
        self.db().tvrage.ensure_index('name', pymongo.ASCENDING)

        # tvdb
        self.db().tvdb.ensure_index('name', pymongo.ASCENDING)

        # blacklists
        self.db().blacklists.ensure_index('group_name', pymongo.ASCENDING)

        # imdb
        self.db().imdb.ensure_index('id', pymongo.ASCENDING)
        self.db().imdb.ensure_index('name', pymongo.ASCENDING)

        # binaries
        self.db().binaries.ensure_index('name', pymongo.ASCENDING)
        self.db().binaries.ensure_index('group_name', pymongo.ASCENDING)
        self.db().binaries.ensure_index('total_parts', pymongo.ASCENDING)

        # parts
        self.db().parts.ensure_index('subject', pymongo.ASCENDING)
        self.db().parts.ensure_index('group_name', pymongo.ASCENDING)

        # releases
        self.db().releases.ensure_index('id', pymongo.ASCENDING)
        self.db().releases.ensure_index('name', pymongo.ASCENDING)
        self.db().releases.ensure_index('search_name', pymongo.ASCENDING)
        self.db().releases.ensure_index('category_id', pymongo.ASCENDING)
        self.db().releases.ensure_index('rage.id', pymongo.ASCENDING)
        self.db().releases.ensure_index('imdb.id', pymongo.ASCENDING)
        self.db().releases.ensure_index('tvdb.id', pymongo.ASCENDING)
        self.db().releases.ensure_index('spotnab_id', pymongo.ASCENDING)
        self.db().releases.ensure_index([
            ('search_name', pymongo.ASCENDING), ('posted', pymongo.ASCENDING)
        ])

    def close(self):
        self.mongo.close()


base = DB()
db = base.db()
fs = base.fs()