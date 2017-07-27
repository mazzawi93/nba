import string
from random import shuffle

import pandas as pd
import numpy as np
from pymongo import MongoClient

from db import process_utils, mongo_utils


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

    match = {
        'difference': {margin: win_margin},
        '_id': {'$nin': ids}}

    if dr:
        # TODO: Add point times
        pipeline = [
            {'$project': {
                'hpts': '$home.pts',
                'apts': '$away.pts',
                'hbet': '$bet.home',
                'abet': '$bet.away',
                'difference': {'$subtract': ['$home.pts', '$away.pts']}

            }},
            {'$match': match},
            {'$limit': 1}
        ]
    else:
        pipeline = [
            {'$project':
                {
                    'hpts': '$home.pts',
                    'apts': '$away.pts',
                    'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
                    'hbet': '$bet.home',
                    'abet': '$bet.away',
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


def dc_dataframe(teams=None, season=None, month=None, bet=False):
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
    mongo = mongo_utils.MongoDB()

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

    games = mongo.aggregate('game_log', pipeline)

    df = pd.DataFrame(list(games))

    if teams is not None:
        hi = np.zeros(len(df), dtype=int)
        ai = np.zeros(len(df), dtype=int)

        # Iterate through each game
        for row in df.itertuples():
            # Team indexes
            hi[row.Index] = teams.index(row.home)
            ai[row.Index] = teams.index(row.away)

        df['home'] = pd.Series(hi, index=df.index)
        df['away'] = pd.Series(ai, index=df.index)

    del df['season']

    return df


def dr_dataframe(model=1, teams=None, season=None, month=None, bet=False):
    """
    Create and return a pandas dataframe for matches that includes the home and away team, and
    times for points scored.

    Reworking it to include extended Dixon Robinson model statistics

    :param month: Calendar Month
    :param season: NBA Season (All stored season selected if None)
    :return: Pandas Dataframe
    """

    # MongoDB
    mongo = mongo_utils.MongoDB()

    df = dc_dataframe(teams, season, month, bet)

    # Don't need week for Dixon Robinson
    del df['week']

    if model > 1:
        for team in ['home', 'away']:

            # Fields we need from mongoDB no matter what the search fields are
            fields = {
                'date': 1,
                'pbp': '$pbp.' + team
            }

            match = {}

            # Prepare season value
            process_utils.season_check(season, fields, match)
            process_utils.month_check(month, fields, match)

            group = {'_id': '$_id'}

            for i in range(1, 5):
                group[team + str(i)] = {'$sum':
                                            {'$cond':
                                                 [{'$and':
                                                       [{'$gte': ['$pbp.time', 12 * i - 1]},
                                                        {'$lt': ['$pbp.time', 12 * i]}]
                                                   }, '$pbp.points', 0]}}

            pipeline = [
                {'$project': fields},
                {'$match': match},
                {'$sort': {'date': 1}},
                {'$unwind': '$pbp'},
                {'$group': group}
            ]

            games = mongo.aggregate('game_log', pipeline)
            games = pd.DataFrame(list(games))

            df = df.merge(games, left_on='_id', right_on='_id', how='inner')

    return df


def player_dataframe(player, season=None):
    """
    Create a dataframe for player stats
    :param player: player id
    :param season: NBA Season
    :return: Pandas DataFrame
    """

    # MongoDB
    mongo = mongo_utils.MongoDB()

    fields = {
        'home': '$home.team',
        'away': '$away.team',
        'home_player': '$players.home.' + player + '.pts',
        'away_player': '$players.away.' + player + '.pts',
        'date': 1
    }

    match = {}

    process_utils.season_check(season, fields, match)

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$sort': {'date': 1}}
    ]

    games = mongo.aggregate('game_log', pipeline)

    # Create DataFrame
    df = pd.DataFrame(list(games))

    # Drop games the player didn't play
    df.dropna(subset=['away_player', 'home_player'], how='all', inplace=True)

    # Determine if player was home or away
    df['is_home'] = pd.notnull(df['home_player'])

    # Combine points into one column
    df.fillna(0, inplace=True)
    df['points'] = df['away_player'] + df['home_player']
    df.drop('away_player', 1, inplace=True)
    df.drop('home_player', 1, inplace=True)

    # Conver team names to Dixon Coles means
    for row in df.itertuples():

        a = mongo.find_one('dixon', {'min_date': {'$lte': row.date}, 'max_date': {'$gte': row.date}})

        try:
            df.set_value(row.Index, 'home', a[row.home]['att'] * a[row.away]['def'] * a['home'])
            df.set_value(row.Index, 'away', a[row.away]['att'] * a[row.home]['def'])
        except TypeError:
            pass

    # Drop irrelevant columns
    try:
        df.drop(['_id', 'date', 'season'], 1, inplace=True)
    except ValueError:
        df.drop(['_id', 'date'], 1, inplace=True)

    return df
