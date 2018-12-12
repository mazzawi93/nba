from pymongo import MongoClient
from pymongo import errors




class Mongo:
    """
    This class is a wrapper for pymongo.  Allows easier use for different collections.
    """

    DIXON_TEAM = 'dixon_team'
    GAME_LOG = 'game_log'

    def __init__(self):
        self.client = MongoClient()
        self.db = self.client.basketball

    def insert(self, collection, doc):

        try:
            self.db[collection].insert(doc)
        except errors.DuplicateKeyError:
            pass

    def count(self, collection, criteria=None):

        return self.db[collection].count(criteria)

    def find(self, collection, query=None, projection=None):

        if projection:
            return self.db[collection].find(query, projection)
        else:
            return self.db[collection].find(query)

    def find_one(self, collection, query=None, projection=None):
        if projection:
            return self.db[collection].find_one(query, projection)
        else:
            return self.db[collection].find_one(query)

    def update(self, collection, query, update):

        return self.db[collection].update(query, update)

    def aggregate(self, collection, pipeline=None):

        return self.db[collection].aggregate(pipeline, allowDiskUse=True)

    def remove(self, collection, query=None):

        return self.db[collection].remove(query)

    def __del__(self):
        self.client.close()
