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

    def db(self):
        """Return the database instance."""
        return self.mongo[self.config['db']]

    def fs(self):
        """Return the GridFS instance for file saves."""
        return gridfs.GridFS(self.mongo[self.config['db']])

    def close(self):
        """Close the MongoDB connection."""
        self.mongo.close()


base = DB()

# allow for "from pynab.db import db, fs"
db = base.db()
fs = base.fs()