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


def dc_dataframe(teams=None, season=None, month=None, bet=False, abilities=False):
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

    # Get the dynamic dixon coles abilities for each team
    if abilities:

        hmean = np.array([])
        amean = np.array([])

        weeks = df.groupby('week')

        for week, games in weeks:
            abilities = mongo.find_one('dixon', {'week': int(week)})

            # Home Team Advantage
            home_adv = abilities.pop('home')

            abilities = pd.DataFrame.from_dict(abilities)

            home = np.array(abilities[games.home])
            away = np.array(abilities[games.away])

            hmean = np.append(hmean, home[0] * away[1] * home_adv)
            amean = np.append(amean, home[1] * away[0])

        df['hmean'] = hmean
        df['amean'] = amean

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


def player_dataframe(season=None, teams=False, poisson=False, beta=False, team_ability=False):
    """
    Create a Pandas DataFrame for player game logs

    :param team_ability: Include team dixon coles abilities
    :param beta: Include player beta values
    :param poisson: Include player poisson mean
    :param teams: Include team parameters in the dataset
    :param season: NBA Season

    :return: DataFrame
    """

    # MongoDB
    mongo = mongo_utils.MongoDB()

    fields = {
        'players': '$players',
        'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
        'date': 1
    }

    match = {}

    process_utils.season_check(season, fields, match)

    player_stats = {'date': 1, 'phome': '$player.home', 'week': 1, 'pts': '$player.pts'}

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$unwind': '$players'},
        {'$group': {'_id': {'game': '$_id', 'player': '$players.player'},
                    'player': {'$first': '$players'},
                    'week': {'$first': '$week'},
                    'date': {'$first': '$date'}}},
        {'$project': player_stats}
    ]

    games = mongo.aggregate('game_log', pipeline)

    df = pd.DataFrame(list(games))
    df = pd.concat([df.drop(['_id'], axis=1), df['_id'].apply(pd.Series)], axis=1)

    # Team Information
    if teams:
        dc = dc_dataframe(season=season, abilities=team_ability)
        df = df.merge(dc, left_on='game', right_on='_id', how='inner')

        for key in ['_id', 'week_y', 'date_y']:
            del df[key]

        df.rename(columns={'week_x': 'week', 'date_x': 'date'}, inplace=True)

    # Player abilities
    if poisson or beta:

        weeks = df.groupby('week')

        if poisson:
            df['mean'] = 0

        if beta:
            df['a'] = 0
            df['b'] = 0

        for week, games in weeks:

            if poisson:

                abilities = mongo.find_one('player_poisson', {'week': int(week)})
                abilities = pd.DataFrame.from_dict(abilities, 'index')

                mean = abilities.loc[games['player']][0]
                df.loc[games.index, 'mean'] = np.array(mean)

            if beta:

                abilities = mongo.find_one('player_beta', {'week': int(week)}, {'_id': 0, 'week': 0})
                abilities = pd.DataFrame.from_dict(abilities, 'index')
                a = abilities.loc[games['player'], 'a']
                b = abilities.loc[games['player'], 'b']
                df.loc[games.index, 'a'] = np.array(a)
                df.loc[games.index, 'b'] = np.array(b)

        df.fillna(0, inplace=True)

    return df
