import string
from random import shuffle
import pandas as pd
import numpy as np

from db import process_utils, mongo


def game_results(season, teams = None):
    """
    Create a Pandas DataFrame that contains game results.

    :param season: NBA Season(s)

    :return: Pandas DataFrame containing game information
    """

    m = mongo.Mongo()

    season_match = {}

    # Match the right season
    if season is not None:
        if isinstance(season, int):
            season = [season]
        season_match = {'season': {'$in': season}}

    pipeline = [
        {'$match': season_match},
        {'$project': {
            'home_team' : '$home.team',
            'away_team' : '$away.team',
            'home_pts': '$home.pts',
            'away_pts': '$away.pts',
            'week': {'$add': [{'$week': '$date'}, {'$multiply': [{'$mod': [{'$year': '$date'}, 2010]}, 52]}]},
            'season': 1,
            'date': 1
        }}

    ]
    # Could aggregate
    cursor = m.aggregate('game_log', pipeline)

    df = pd.DataFrame(list(cursor))

    # If team names are included, replace index numbers
    if teams is not None:
        hi = np.zeros(len(df), dtype=int)
        ai = np.zeros(len(df), dtype=int)

        # Iterate through each game
        for row in df.itertuples():
            # Team indexes
            hi[row.Index] = teams.index(row.home_team)
            ai[row.Index] = teams.index(row.away_team)

        df['home_team'] = pd.Series(hi, index=df.index)
        df['away_team'] = pd.Series(ai, index=df.index)

    return df


def betting_df(season = None, sportsbooks = None):
    """
    Create a Pandas DataFrame that contains betting information by game/sportsbook.

    :param season: NBA Season(s)
    :param sportsbook: Sportsbook name(s)

    :return: Pandas DataFrame containing odds information
    """

    m = mongo.Mongo()

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
        {'$project': {'sportsbook': '$odd.sportsbook', 'home_odds': '$odd.home_odds', 'away_odds': '$odd.away_odds'}},
        {'$match': sportsbook_match}
    ]

    cursor = m.aggregate('game_log', pipeline)

    df = pd.DataFrame(list(cursor))

    return df


def team_abilities(mw, att_constraint, def_constraint):
    """
    Return abilities based on the time decay factor

    :param mw: Time decay factor

    :return: Pandas DataFrames: Team abilities and home court advantage
    """

    m = mongo.Mongo()
    query = m.find('dixon_team',
                   {'mw': mw, 'att_constraint': att_constraint, 'def_constraint': def_constraint},
                   {'_id': 0, 'model': 0, 'mw':0, 'att_constraint': 0, 'def_constraint': 0})

    # The attack and defence columns are dicts, so need to expand them and then
    # melt so that each row is a team/week
    df = pd.DataFrame(list(query))

    attack = pd.DataFrame(df.att.values.tolist())
    attack['week'] = df['week']
    attack = attack.melt('week', var_name = 'team', value_name = 'attack')

    defence = pd.DataFrame(df['def'].values.tolist())
    defence['week'] = df['week']
    defence = defence.melt('week', var_name = 'team', value_name = 'defence')

    home_adv = pd.DataFrame(df['home_adv'].values.tolist())
    home_adv['week'] = df['week']
    home_adv = home_adv.melt('week', var_name = 'team', value_name = 'home_adv')

    df = attack.merge(defence)
    df = df.merge(home_adv)

    return df
