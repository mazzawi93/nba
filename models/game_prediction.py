import numpy as np
from scipy.stats import beta
from scipy.stats import bernoulli

from db import datasets, mongo
from models import prediction_utils as pu
import pandas as pd


def dixon_prediction(season, abilities=None, mw=0, players=False, star=False, penalty=0.4, star_factor=80):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    games = datasets.game_dataset(season=season, abilities=True, mw=mw, players=players)

    hprob = np.zeros(len(games))
    aprob = np.zeros(len(games))

    if players:
        games['hpen'], games['apen'] = pu.player_penalty(games, mw, penalty, star_factor, star)
    else:
        games['hpen'], games['apen'] = 1, 1

    # Iterate through each game to determine the winner and prediction
    for row in games.itertuples():

        if abilities is not None:
            hmean = abilities[row.home]['att'] * abilities[row.away]['def'] * abilities['home']
            amean = abilities[row.away]['att'] * abilities[row.home]['def']
        else:
            hmean = row.hmean
            amean = row.amean

        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(hmean * row.hpen, amean * row.apen)

    # Scale odds so they add to 1
    scale = 1 / (hprob + aprob)
    hprob = hprob * scale
    aprob = aprob * scale

    # Actual match winners
    winners = np.where(games.hpts > games.apts, games.home, games.away)
    predictions = np.where(hprob > aprob, games.home, games.away)

    outcomes = pd.DataFrame({'winner': winners, 'prediction': predictions, 'month': games.date.dt.month,
                             'correct': np.equal(winners, predictions),
                             'season': games.season, 'hprob': hprob, 'aprob': aprob})

    return outcomes


def poisson_prediction(season, mw=0.0394):
    players = datasets.player_dataframe(season, poisson=True, mw=mw)
    games = datasets.game_dataset(season=season)

    games['hmean'], games['amean'] = 0, 0

    for _id, stats in players.groupby('game'):

        hp = np.sum(np.nan_to_num(np.where(stats.phome, stats.poisson, 0)))
        ap = np.sum(np.nan_to_num(np.where(stats.phome, 0, stats.poisson)))

        index = games[games._id == _id].index[0]


        # Set the values
        games.loc[index, 'hmean'] = hp
        games.loc[index, 'amean'] = ap

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    for row in games.itertuples():

        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean, row.amean)

    # Actual match winners
    winners = np.where(games.hpts > games.apts, games.home, games.away)
    predictions = np.where(hprob > aprob, games.home, games.away)

    outcomes = pd.DataFrame({'winner': winners, 'prediction': predictions, 'month': games.date.dt.month,
                             'prob': np.maximum(hprob, aprob), 'correct': np.equal(winners, predictions),
                             'season': games.season})

    return outcomes


def beta_prediction(season, mw=0.0394):

    players = datasets.player_dataframe(season, beta=True, mw=mw)
    games = datasets.game_dataset(season=season, abilities=True)

    games['hbeta'], games['abeta'] = 0, 0

    for _id, stats in players.groupby('game'):

        hp = np.sum(np.nan_to_num(np.where(stats.phome, beta.mean(stats.a, stats.b), 0)))
        ap = np.sum(np.nan_to_num(np.where(stats.phome, 0, beta.mean(stats.a, stats.b))))

        index = games[games._id == _id].index[0]

        # Set the values
        games.loc[index, 'hbeta'] = hp
        games.loc[index, 'abeta'] = ap

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean * row.hbeta, row.amean * row.abeta)

    # Actual match winners
    winners = np.where(games.hpts > games.apts, games.home, games.away)
    predictions = np.where(hprob > aprob, games.home, games.away)

    outcomes = pd.DataFrame({'winner': winners, 'prediction': predictions, 'month': games.date.dt.month,
                             'prob': np.maximum(hprob, aprob), 'correct': np.equal(winners, predictions),
                             'season': games.season})

    return outcomes