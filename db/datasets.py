import string
from random import shuffle

import pandas as pd
import numpy as np
from pymongo import MongoClient

from db import process_utils


def select_match(win_margin, ids, dr):
    """
    Select a match from game logs with a given winning margin
    :param dr: True for DixonRobinson model, False for dc
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
    same_project = {
        'hpts': '$home.pts',
        'apts': '$away.pts',
        'difference': {'$subtract': ['$home.pts', '$away.pts']}
    }

    match = {
        'difference': {margin: win_margin},
        '_id': {'$nin': ids}}

    if dr:
        # TODO: Add point times
        pipeline = [
            {'$project': same_project},
            {'$match': match},
            {'$limit': 1}
        ]
    else:
        # TODO: Add weeks
        pipeline = [
            {'$project':
                {
                    'hpts': '$home.pts',
                    'apts': '$away.pts',
                    'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
                    'difference': {'$subtract': ['$home.pts', '$away.pts']}
                }},
            {'$match': match},
            {'$limit': 1}
        ]

    game = collection.aggregate(pipeline)

    # The limit is 1, so just return the first object
    for i in game:
        return i


def create_test_set(t, g, margin, dr=True):
    """
    Create test set based on the number of teams and games played per team.
    Games are taken from the game_log mongodb collection based on the winning
    margin.  Games will only be selected once to have a unique test set.

    This test set will be used to validate the model because the first team
    will be the strongest, second will be second strongest and so on.

    :param dr: True for DixonRobinson model, False for DixonColes
    :param t: The number of teams
    :param g: The number of games played between a set of two teams (Must be even.)
    :param margin: The winning margin
    :return: Pandas Dataframe containing data (Points per team (total and time stamps))
    """

    if t < 2:
        raise ValueError('There must be at least two teams.')

    # G must be even so that there is an equal number of home and away games
    if g % 2 != 0:
        raise ValueError('The number of games must be even so there is equal home and away')

    data = []
    teams = []

    # Ids of games taken from MongoDB to keep a unique test set
    ids = []

    # Give out team names in order so we always know the order of strength
    for i in range(t):
        if i < 26:
            teams.append(string.ascii_uppercase[i])
        else:
            teams.append(string.ascii_uppercase[i - 26] + string.ascii_uppercase[i - 26])

    x = 0
    for team in teams:

        # Iterate through the teams so that each team plays each other n times.
        # The teams play each other the same amount at home and away
        for i in range(t - 1, x, -1):

            # The number of games two teams play against each other
            for j in range(g):

                game = {}

                # Split matches so teams are playing home and away evenly
                if j % 2 == 0:
                    game['home'] = teams.index(team)
                    game['away'] = i
                    match = select_match(margin, ids, dr)
                else:
                    game['home'] = i
                    game['away'] = teams.index(team)
                    match = select_match(-margin, ids, dr)

                # Append the id to the list so that the match doesn't get selected again
                ids.append(match['_id'])

                del match['_id']
                del match['difference']
                game.update(match)

                data.append(game)

        x += 1

    shuffle(data)
    return pd.DataFrame(data)


def dc_dataframe(teams, season=None, month=None, bet=False):
    """
    Create a Pandas DataFrame for the Dixon and Coles model that uses final scores only.
    Can specify the NBA season, month and if betting information should be included.

    :param teams: Team names
    :param season: NBA Season
    :param month: Calendar Month
    :param bet: Betting Lines
    :return: Pandas DataFrame
    """

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    fields = {
        'home': '$home.team',
        'away': '$away.team',
        'hpts': '$home.pts',
        'apts': '$away.pts',
        'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
        'date': 1,
    }

    match = {}

    process_utils.season_check(season, fields, match)
    process_utils.month_check(month, fields, match)

    if bet:
        fields['hbet'] = '$bet.home'
        fields['abet'] = '$bet.away'

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$sort': {'date': 1}}
    ]

    games = collection.aggregate(pipeline, allowDiskUse=True)

    df = pd.DataFrame(list(games))

    hi = np.zeros(len(df), dtype=int)
    ai = np.zeros(len(df), dtype=int)

    # Iterate through each game
    for row in df.itertuples():
        # Team indexes
        hi[row.Index] = teams.index(row.home)
        ai[row.Index] = teams.index(row.away)

    df['home'] = pd.Series(hi, index=df.index)
    df['away'] = pd.Series(ai, index=df.index)

    # Remove unnecessary information
    del df['_id']
    del df['season']
    del df['date']

    return df


def dr_dataframe(teams, season=None, month=None, bet=False):
    """
    Create and return a pandas dataframe for matches that includes the home and away team, and
    times for points scored.

    :param month: Calendar Month
    :param season: NBA Season (All stored season selected if None)
    :return: Pandas Dataframe
    """

    # MongoDB
    client = MongoClient()
    db = client.basketball
    collection = db.game_log

    # Fields we need from mongoDB no matter what the search fields are
    fields = {
        'home': '$home.team',
        'away': '$away.team',
        'hpts': '$home.pts',
        'apts': '$away.pts',
        'date': 1,
    }

    if bet:
        fields['hbet'] = '$bet.home'
        fields['abet'] = '$bet.away'

    match = {}

    # Prepare season value
    process_utils.season_check(season, fields, match)
    process_utils.month_check(month, fields, match)

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$sort': {'date': 1}}
    ]

    games = collection.aggregate(pipeline, allowDiskUse=True)

    df = pd.DataFrame(list(games))

    hi = np.zeros(len(df), dtype=int)
    ai = np.zeros(len(df), dtype=int)

    # Iterate through each game
    for row in df.itertuples():
        # Team indexes
        hi[row.Index] = teams.index(row.home)
        ai[row.Index] = teams.index(row.away)

    df['home'] = pd.Series(hi, index=df.index)
    df['away'] = pd.Series(ai, index=df.index)

    # Remove unnecessary information
    del df['_id']
    del df['season']
    del df['date']

    return df
