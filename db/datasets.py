""" Mongo Aggregations into Pandas DataFrames. """

import pandas as pd
import numpy as np
from db import mongo
from scipy.stats import beta

def game_results(season=None, teams=None, date=None):
    """
    Creates a Pandas DataFrame that contains game results.

    Args:
        season: A list of season numbers
        teams: Team Names, if it's not None the DataFrame will contain indices

    Returns:
        A Pandas DataFrame containing a historical NBA results.

    """

    mongo_wrapper = mongo.Mongo()

    season_match = {}

    # Match the right season
    if season is not None:
        if isinstance(season, int):
            season = [season]
        season_match['season'] = {'$in': season}

    date_match = {}
    if date is not None:
        date_match['date'] = {'$lt': date}

    pipeline = [
        {'$match': season_match},
        {'$project': {
            'home_team' : '$home.team',
            'away_team' : '$away.team',
            'home_pts': '$home.pts',
            'away_pts': '$away.pts',
            'season': 1,
            'date': 1
        }},
        {'$match': date_match}

    ]
    # Could aggregate
    cursor = mongo_wrapper.aggregate(mongo_wrapper.GAME_LOG, pipeline)

    games_df = pd.DataFrame(list(cursor))

    # If team names are included, replace index numbers
    if teams is not None:
        home_index = np.zeros(len(games_df), dtype=int)
        away_index = np.zeros(len(games_df), dtype=int)

        # Iterate through each game
        for row in games_df.itertuples():
            # Team indexes
            home_index[row.Index] = teams.index(row.home_team)
            away_index[row.Index] = teams.index(row.away_team)

        games_df['home_team'] = pd.Series(home_index, index=games_df.index)
        games_df['away_team'] = pd.Series(away_index, index=games_df.index)

    return games_df


def betting_df(season=None, sportsbooks=None):
    """
    Creates a Pandas DataFrame that contains betting information by game/sportsbook.

    Args:
        season: List of NBA Seasons
        sportsbooks: List of sportsbook names

    Returns:
        A Pandas DataFrame containing odds information
    """

    mongo_wrapper = mongo.Mongo()

    season_match = {}
    sportsbook_match = {}

    # Match the right season
    if season is not None:
        if isinstance(season, int):
            season = [season]
        season_match = {'season': {'$in': season}}

    # Match the right sportsbook
    if sportsbooks is not None:
        if isinstance(sportsbooks, str):
            sportsbooks = [sportsbooks]
        sportsbook_match = {'sportsbook': {'$in': sportsbooks}}

    # Mongo Aggregation
    pipeline = [
        {'$match': season_match},
        {'$project': {'odd': '$odds.sportsbooks'}},
        {'$unwind': '$odd'},
        {'$project': {'sportsbook': '$odd.sportsbook',
                      'home_odds': '$odd.home_odds',
                      'away_odds': '$odd.away_odds'}},
        {'$match': sportsbook_match}
    ]

    cursor = mongo_wrapper.aggregate(mongo_wrapper.GAME_LOG, pipeline)

    return pd.DataFrame(list(cursor))


def player_abilities(decay, day_span):

    query = {
        'mw': decay,
        'day_span': day_span
    }

    projection = {
        '_id': 0,
        'mw': 0,
        'day_span': 0,
    }

    mongo_wrapper = mongo.Mongo()
    cursor = mongo_wrapper.find(mongo_wrapper.PLAYERS_BETA, query, projection)

    abilities_df = pd.DataFrame(list(cursor))

    df = pd.concat([abilities_df.drop(['player'], axis=1), abilities_df['player'].apply(pd.Series)], axis = 1)

    df['mean'] = beta.mean(df.a, df.b)

    return df


def team_abilities(decay, att_constraint, def_constraint, day_span):
    """
    Return abilities based on the time decay factor

    Args:
        decay: Time decay parameter
        att_constraint: Mean Attack Constraint of the model
        def_constraint: Mean Defence Constraint of the model

    Returns:
        Pandas DataFrame of team parameters by week
    """

    query = {
        'mw': decay,
        'att_constraint': att_constraint,
        'def_constraint': def_constraint,
        'day_span': day_span
    }

    projection = {
        '_id': 0,
        'model': 0,
        'mw': 0,
        'att_constraint': 0,
        'def_constraint': 0
    }

    mongo_wrapper = mongo.Mongo()
    cursor = mongo_wrapper.find(mongo_wrapper.DIXON_TEAM, query, projection)

    # The attack and defence columns are dicts, so need to expand them and then
    # melt so that each row is a team/week
    abilities_df = pd.DataFrame(list(cursor))

    attack = pd.DataFrame(abilities_df.att.values.tolist())
    attack['date'] = abilities_df['date']
    attack = attack.melt('date', var_name='team', value_name='attack')

    defence = pd.DataFrame(abilities_df['def'].values.tolist())
    defence['date'] = abilities_df['date']
    defence = defence.melt('date', var_name='team', value_name='defence')

    home_adv = pd.DataFrame(abilities_df['home_adv'].values.tolist())
    home_adv['date'] = abilities_df['date']
    home_adv = home_adv.melt('date', var_name='team', value_name='home_adv')

    abilities_df = attack.merge(defence)
    abilities_df = abilities_df.merge(home_adv)

    return abilities_df

def player_results(season=None, date = None):

    # MongoDB
    m = mongo.Mongo()

    season_match = {}

    # Match the right season
    if season is not None:
        if isinstance(season, int):
            season = [season]
        season_match['season'] = {'$in': season}

    date_match = {}
    if date is not None:
        date_match['date'] = {'$lt': date}

    df = None

    for i in [['$hplayers.player', '$hplayers.pts', '$home.team', '$home.pts'], ['$aplayers.player', '$aplayers.pts', '$away.team', '$away.pts']]:
        pipeline = [
            {'$match': season_match},
            {'$match': date_match},
            {'$project': {
                'player': i[0],
                'pts': i[1],
                'team': i[2],
                'team_pts': i[3],
                'date': 1,
                'season': 1
            }},
            {'$unwind': {
                'path': '$player',
                'includeArrayIndex': 'player_index'
            }},
            {'$unwind': {
                'path': '$pts',
                'includeArrayIndex': 'pts_index'
            }},
            {'$project': {
                'date': 1,
                'team': 1,
                'season': 1,
                'player': 1,
                'pts': 1,
                'team_pts': 1,
                'compare': {
                    '$cmp': ['$player_index', '$pts_index']
                }
            }},
            {'$match': {'compare': 0}}
        ]

        games = m.aggregate('game_log', pipeline)

        if df is None:
            df = pd.DataFrame(list(games))
        else:
            df = pd.concat([df, pd.DataFrame(list(games))])

    return df
