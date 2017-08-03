from db import mongo_utils, process_utils
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt


def point_times_chart(season):
    """
    Create a bar graph of point times to see the pattern
    :param season: NBA Season
    """
    # MongoDB
    mongo = mongo_utils.MongoDB()

    fields = {
        'pbp_home': '$pbp.home',
        'pbp_away': '$pbp.away'
    }

    match = {}

    process_utils.season_check(season, fields, match)

    home_pipeline = [
        {'$project': {'pbp': '$pbp.home',
                      'season': 1}},
        {'$match': match},
        {'$unwind': '$pbp'},
        {'$match': {'pbp.points': {'$exists': True}}},
        {'$project': {'points': '$pbp.points',
                      'time': '$pbp.time',
                      '_id': 0}}
    ]

    away_pipeline = [
        {'$project': {'pbp': '$pbp.away',
                      'season': 1}},
        {'$match': match},
        {'$unwind': '$pbp'},
        {'$match': {'pbp.points': {'$exists': True}}},
        {'$project': {'points': '$pbp.points',
                      'time': '$pbp.time',
                      '_id': 0}}
    ]

    home_games = mongo.aggregate('game_log', home_pipeline)
    away_games = mongo.aggregate('game_log', away_pipeline)

    hdf = pd.DataFrame(list(home_games))
    adf = pd.DataFrame(list(away_games))

    # Convert Times to int for ease
    hdf.time = hdf.time.astype(int)
    adf.time = hdf.time.astype(int)

    # Remove Overtime
    hdf = hdf[hdf.time < 48]
    adf = adf[adf.time < 48]

    # Points per minute
    hp = hdf.groupby('time')['points'].sum()
    ap = adf.groupby('time')['points'].sum()
    totals = hp + ap

    # Point Distribution
    plt.bar(np.arange(0, 48), totals, color='c', width=1, edgecolor='k', linewidth=0.75)
    plt.xlabel('Time (Minute)')
    plt.ylabel('Points')
    plt.show()

    return totals
