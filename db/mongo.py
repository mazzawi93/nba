from pymongo import MongoClient
from pymongo import errors

class Mongo:
    """
    This class is a wrapper for pymongo.  Allows easier use for different collections.
    """

    DIXON_TEAM = 'dixon_team'
    GAME_LOG = 'game_log'
    PLAYERS_BETA = 'player_beta'

    def __init__(self):
        self.client = MongoClient()
        self.database = self.client.basketball

    def insert(self, collection, doc):

        try:
            self.database[collection].insert(doc)
        except errors.DuplicateKeyError:
            pass

    def count(self, collection, criteria=None):

        return self.database[collection].count(criteria)

    def find(self, collection, query=None, projection=None):

        if projection:
            return self.database[collection].find(query, projection)

        return self.database[collection].find(query)

    def find_one(self, collection, query=None, projection=None):
        if projection:
            return self.database[collection].find_one(query, projection)

        return self.database[collection].find_one(query)

    def update(self, collection, query, update):

        return self.database[collection].update(query, update)

    def aggregate(self, collection, pipeline=None):
        """
        Wrapper for the pymongo aggregation function.

        https://docs.mongodatabase.com/manual/aggregation/

        """

        return self.database[collection].aggregate(pipeline, allowDiskUse=True)

    def remove(self, collection, query=None):

        return self.database[collection].remove(query)

    def __del__(self):
        self.client.close()
