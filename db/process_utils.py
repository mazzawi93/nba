import string
from db import mongo

teams = ['ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM',
         'MIA', 'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHO', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS']


def season_check(season, fields, match):
    """
    Add season to the mongoDB query fields
    :param season: NBA season
    :param fields: MongoDB $project fields
    :param match: MongoDB $match field
    """

    if season is not None:

        # Convert season to list because aggregation uses $in
        if isinstance(season, int):
            season = [season]

        # Raise error if incorrect type was given
        if not isinstance(season, list):
            raise TypeError("Season must be a list for query purposes")
        else:
            # Raise error if year value is incorrect
            for year in season:
                if year < 2013 or year > 2017:
                    raise ValueError("Years must be within the range 2013-2017")

            # Add season for aggregation query
            fields['season'] = 1
            match['season'] = {'$in': season}


def name_teams(test, nteams=None):
    """
    Team names for the datasets.

    :param test: True for fabricated dataset.  Team names become letters
    :param nteams: Number of teams
    :return: Team names
    """

    # Return nba team names
    if test is False:
        return teams
    # Assign letters of the alphabet as team names
    else:
        team_names = []
        for i in range(nteams):
            if i < 26:
                team_names.append(string.ascii_uppercase[i])
            else:
                team_names.append(string.ascii_uppercase[i - 26] + string.ascii_uppercase[i - 26])

        return team_names


def select_match(win_margin, ids):
    """
    Select a match from game logs with a given winning margin

    :param ids: List of game IDs to exclude
    :param win_margin: Win margin of the game, negative means the away team won.
    :return: The game selected from MongoDB
    """

    # Connect to MongoDB
    m = mongo.Mongo()

    # Negative win margin means the away team won
    if win_margin < 0:
        margin = '$lte'
    else:
        margin = '$gte'

    # Match information
    match = {
        'difference': {margin: win_margin},
        '_id': {'$nin': ids}}

    # MongoDB Pipeline
    pipeline = [
        {'$project':
            {
                'hpts': '$home.pts',
                'apts': '$away.pts',
                'difference': {'$subtract': ['$home.pts', '$away.pts']}
            }},
        {'$match': match},
        {'$limit': 1}
    ]

    game = m.aggregate('game_log', pipeline)

    # The limit is 1, so just return the first object
    for i in game:
        return i