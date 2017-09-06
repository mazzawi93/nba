import string
from random import shuffle

import pandas as pd
import numpy as np
from pymongo import MongoClient

from db import process_utils, mongo


def create_test_set(t, g, margin):
    """
    Create test set based on the number of teams and games played per team.
    Games are taken from the game_log mongodb collection based on the winning
    margin.  Games will only be selected once to have a unique test set.

    This test set will be used to validate the model because the first team
    will be the strongest, second will be second strongest and so on.

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
                    match = process_utils.select_match(margin, ids)
                else:
                    game['home'] = i
                    game['away'] = teams.index(team)
                    match = process_utils.select_match(-margin, ids)

                # Append the id to the list so that the match doesn't get selected again
                ids.append(match['_id'])

                del match['_id']
                del match['difference']
                game.update(match)

                data.append(game)

        x += 1

    shuffle(data)
    return pd.DataFrame(data)


def game_dataset(teams=None, season=None, bet=False, abilities=False, mw=0.0394, players=False):
    """
    Create a Pandas DataFrame for the Dixon and Coles model that uses final scores only.
    Can specify the NBA season, month and if betting information should be included.

    :param teams: Team names
    :param season: NBA Season
    :param bet: Betting Lines
    :param players: Include player ID's
    :param mw: Match weight for abilities
    :param abilities: Include team abilities previously generated

    :return: Pandas DataFrame containing game information
    """

    # MongoDB
    m = mongo.Mongo()

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

    # Include betting odds
    if bet:
        fields['hbet'] = '$bet.home'
        fields['abet'] = '$bet.away'

    # Include players
    if players:
        fields['hplayers'] = '$hplayers.player'
        fields['aplayers'] = '$aplayers.player'

    # Mongo Pipeline
    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$sort': {'date': 1}}
    ]

    games = m.aggregate('game_log', pipeline)

    df = pd.DataFrame(list(games))

    # If team names are included, replace index numbers
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

        for week, games in df.groupby('week'):
            ab = m.find_one('dixon_team', {'week': int(week), 'mw': mw})

            if ab is None:
                raise ValueError('Abilities don\'t exist for that match weight')

            # Home Team Advantage
            home_adv = ab.pop('home')

            ab = pd.DataFrame.from_dict(ab)

            home = np.array(ab[games.home])
            away = np.array(ab[games.away])

            hmean = np.append(hmean, home[0] * away[1] * home_adv)
            amean = np.append(amean, home[1] * away[0])

        df['hmean'] = hmean
        df['amean'] = amean

    return df


def player_position(season):
    """
    Get the position that each player played in a season.

    :param season: NBA Season

    :return: DataFrame containing player positions
    """

    # Mongo
    m = mongo.Mongo()

    # Needs to be a list
    if isinstance(season, int):
        season = [season]

    fields = {'seasons': '$seasons'}

    pipeline = [
        {'$project': fields},
        {'$unwind': '$seasons'},
        {'$match': {'seasons.season': {'$in': season}}},
        {'$group': {'_id': {'player': '$_id', 'season': '$seasons.season'},
                    'pos': {'$first': '$seasons.pos'}}},
    ]

    players = m.aggregate('player_season', pipeline)

    df = pd.DataFrame(list(players))
    df = pd.concat([df.drop(['_id'], axis=1), df['_id'].apply(pd.Series)], axis=1)

    # Replace the hybrid positions with their main position
    df.replace('SF-PF', 'SF', inplace=True)
    df.replace('PF-SF', 'PF', inplace=True)
    df.replace('SG-PG', 'SG', inplace=True)
    df.replace('SF-SG', 'SF', inplace=True)
    df.replace('PG-SG', 'PG', inplace=True)
    df.replace('SG-SF', 'SG', inplace=True)
    df.replace('PF-C', 'PF', inplace=True)
    df.replace('C-PF', 'C', inplace=True)

    return df


def player_dataset(season=None, teams=False, position=False, team_ability=False, poisson=False,
                   mw=0.0394, beta=False):
    """
    Create a Pandas DataFrame for player game logs

    :param team_ability: Include team dixon coles abilities
    :param teams: Include team parameters in the dataset
    :param season: NBA Season
    :param beta: Include player's beta mean
    :param mw: Match weight
    :param poisson: Include player poisson abilities
    :param position: Include Player positions

    :return: DataFrame
    """

    # MongoDB
    m = mongo.Mongo()

    fields = {
        'players': '$players',
        'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
        'date': 1,
    }

    match = {}

    process_utils.season_check(season, fields, match)

    player_stats = {'date': 1, 'phome': '$player.home', 'week': 1, 'pts': '$player.pts', 'season': 1,
                    'fouls': '$player.fouls'}

    pipeline = [
        {'$project': fields},
        {'$match': match},
        {'$unwind': '$players'},
        {'$group': {'_id': {'game': '$_id', 'player': '$players.player'},
                    'player': {'$first': '$players'},
                    'week': {'$first': '$week'},
                    'season': {'$first': '$season'},
                    'date': {'$first': '$date'}}},
        {'$project': player_stats}
    ]

    games = m.aggregate('game_log', pipeline)

    df = pd.DataFrame(list(games))
    df = pd.concat([df.drop(['_id'], axis=1), df['_id'].apply(pd.Series)], axis=1)

    # Team Information
    if teams or team_ability:
        dc = game_dataset(season=season, abilities=team_ability)
        df = df.merge(dc, left_on=['game', 'season'], right_on=['_id', 'season'], how='inner')

        for key in ['_id', 'week_y', 'date_y']:
            del df[key]

        df.rename(columns={'week_x': 'week', 'date_x': 'date'}, inplace=True)

    # Player positions
    if position:
        pos_df = player_position(season)
        df = df.merge(pos_df, left_on=['player', 'season'], right_on=['player', 'season'])

    # Player abilities
    if poisson or beta:

        weeks = df.groupby('week')

        if poisson:
            df['poisson'] = 0

        if beta:
            df['a'] = 0
            df['b'] = 0

        for week, games in weeks:

            if poisson:
                abilities = mongo.find_one('player_poisson', {'week': int(week), 'mw': mw},
                                           {'_id': 0, 'week': 0, 'mw': 0})
                abilities = pd.DataFrame.from_dict(abilities, 'index')

                mean = abilities.loc[games['player']][0]
                df.loc[games.index, 'poisson'] = np.array(mean)

            if beta:
                abilities = mongo.find_one('player_beta', {'week': int(week), 'mw': mw}, {'_id': 0, 'week': 0, 'mw': 0})
                abilities = pd.DataFrame.from_dict(abilities, 'index')

                a = abilities.loc[games['player'], 'a']
                b = abilities.loc[games['player'], 'b']
                df.loc[games.index, 'a'] = np.array(a)
                df.loc[games.index, 'b'] = np.array(b)

    df.fillna(0, inplace=True)

    return df
