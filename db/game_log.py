from pymongo import MongoClient


def select_match(win_margin, ids):
    """
    Select a match from game logs with a given winning margin
    :param ids: List of game ids to exclude
    :param win_margin: Win margin of the game, negative means the away team won.
    :return: The game selected from MongoDB
    """

    # Connect to MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    # Negative win margin means the away team won
    if win_margin < 0:
        margin = '$lte'
    else:
        margin = '$gte'

    # MongoDB Aggregation
    pipeline = [
        {'$project':
            {
                'home_time.points': 1,
                'away_time.points': 1,
                'home_time.time': 1,
                'away_time.time': 1,
                'home.pts': 1,
                'away.pts': 1,
                'difference': {'$subtract': ['$home.pts', '$away.pts']}
            }},
        {'$match':
            {
                'difference': {margin: win_margin},
                '_id': {'$nin': ids}
            }},
        {'$limit': 1}
    ]

    game = collection.aggregate(pipeline)

    # The limit is 1, so just return the first object
    for i in game:
        return i
