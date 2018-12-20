""" Mongo Aggregations into Pandas DataFrames. """

import pandas as pd
import numpy as np
from db import mongo

def game_results(season=None, teams=None, week=None):
    """
    Creates a Pandas DataFrame that contains game results.

    Args:
        season: A list of season numbers
        teams: Team Names, if it's not None the DataFrame will contain indices
        week: Week number

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

    week_match = {}
    if week is not None:
        week_match['week'] = {'$lt': week}

    pipeline = [
        {'$match': season_match},
        {'$project': {
            'home_team' : '$home.team',
            'away_team' : '$away.team',
            'home_pts': '$home.pts',
            'away_pts': '$away.pts',
            'week': {'$add': [{'$week': '$date'},
                              {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
            'season': 1,
            'date': 1
        }},
        {'$match': week_match}

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


def team_abilities(decay, att_constraint, def_constraint):
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
        'week': {'$exists': True}
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
    attack['week'] = abilities_df['week']
    attack = attack.melt('week', var_name='team', value_name='attack')

    defence = pd.DataFrame(abilities_df['def'].values.tolist())
    defence['week'] = abilities_df['week']
    defence = defence.melt('week', var_name='team', value_name='defence')

    home_adv = pd.DataFrame(abilities_df['home_adv'].values.tolist())
    home_adv['week'] = abilities_df['week']
    home_adv = home_adv.melt('week', var_name='team', value_name='home_adv')

    abilities_df = attack.merge(defence)
    abilities_df = abilities_df.merge(home_adv)

    return abilities_df
