from db import mongo_utils, process_utils
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import poisson, beta


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


def poisson_distribution(mu, color, dist='pmf'):

    if dist != 'pmf' and dist != 'cdf':
        raise ValueError

    x = np.arange(0, 21)

    if dist == 'pmf':
        y = poisson.pmf(mu=mu, k=x)
        ylabel = 'Pr(X=k)'
    else:
        y = poisson.cdf(mu=mu, k=x)
        ylabel = 'Pr(X' + r'$\leq$' + 'k)'

    plt.plot(x, y, 'k-', linewidth=0.5)
    plt.plot(x, y, color + 'o', label=r'$\lambda = $' + str(mu))
    plt.xticks(np.arange(0,21,5))
    plt.xlabel('k')
    plt.ylabel(ylabel)
    plt.legend()


def beta_distribution(a, b, color, dist='pdf'):


    if dist != 'pdf' and dist != 'cdf':
        raise ValueError

    x = np.arange(0, 1, 0.01)

    if dist == 'pdf':
        y = beta.pdf(x, a, b)
        ylabel = 'PDF'
    else:
        y = beta.cdf(x, a, b)
        ylabel = 'CDF'

    plt.plot(x, y, color + '-', label=r'$\alpha = $' + str(a) + '  ' + r'$\beta = $' + str(b))
    plt.ylabel(ylabel)
    plt.legend()