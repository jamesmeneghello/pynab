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
        """Create a MongoDB connection for use."""
        #TODO: txMongo
        self.mongo = pymongo.MongoClient(self.config['host'], self.config['port'])
        self.create_indexes()

    def db(self):
        """Return the database instance."""
        return self.mongo[self.config['db']]

    def fs(self):
        """Return the GridFS instance for file saves."""
        return gridfs.GridFS(self.mongo[self.config['db']])

    def create_indexes(self):
        """Ensures that indexes for collections exist.
        Add all new appropriate indexes here. Gets called
        once per script run."""
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
        self.db().tvrage.ensure_index('_id', pymongo.ASCENDING, background=True)
        self.db().tvrage.ensure_index('name', pymongo.ASCENDING, background=True)

        # tvdb
        self.db().tvdb.ensure_index('_id', pymongo.ASCENDING)
        self.db().tvdb.ensure_index('name', pymongo.ASCENDING)

        # blacklists
        self.db().blacklists.ensure_index('group_name', pymongo.ASCENDING)

        # imdb
        self.db().imdb.ensure_index('_id', pymongo.ASCENDING)
        self.db().imdb.ensure_index('name', pymongo.ASCENDING)

        # binaries
        self.db().binaries.ensure_index('name', pymongo.ASCENDING, background=True)
        self.db().binaries.ensure_index('group_name', pymongo.ASCENDING, background=True)
        self.db().binaries.ensure_index('total_parts', pymongo.ASCENDING, background=True)

        # parts
        self.db().parts.ensure_index('subject', pymongo.ASCENDING, background=True)
        self.db().parts.ensure_index('group_name', pymongo.ASCENDING, background=True)

        # releases
        self.db().releases.ensure_index('id', pymongo.ASCENDING)
        self.db().releases.ensure_index('name', pymongo.ASCENDING)
        self.db().releases.ensure_index([
            ('search_name', 'text')
        ])
        self.db().releases.ensure_index('category._id', pymongo.ASCENDING, background=True)
        self.db().releases.ensure_index('rage._id', pymongo.ASCENDING, background=True)
        self.db().releases.ensure_index('imdb._id', pymongo.ASCENDING, background=True)
        self.db().releases.ensure_index('tvdb._id', pymongo.ASCENDING, background=True)
        self.db().releases.ensure_index([
                                            ('tvrage._id', pymongo.ASCENDING),
                                            ('category._id', pymongo.ASCENDING)
                                        ], background=True)
        self.db().releases.ensure_index([
                                            ('posted', pymongo.ASCENDING),
                                            ('category._id', pymongo.ASCENDING)
                                        ], background=True)
        self.db().releases.ensure_index([
                                            ('posted', pymongo.ASCENDING),
                                            ('tvrage._id', pymongo.ASCENDING),
                                            ('category._id', pymongo.ASCENDING)
                                        ], background=True)

    def close(self):
        """Close the MongoDB connection."""
        self.mongo.close()


base = DB()

# allow for "from pynab.db import db, fs"
db = base.db()
fs = base.fs()