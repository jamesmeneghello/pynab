import pymongo

class DB:
    def __init__(self, config):
        self.config = config
        self.connect()

    def connect(self):
        self.mongo = pymongo.MongoClient(self.config['host'], self.config['port'])

    def db(self):
        return self.mongo[self.config['db']]

    def close(self):
        self.mongo.close()