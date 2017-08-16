import numpy as np
from scipy.stats import beta

from db import datasets, mongo_utils
from models import prediction_utils as pu
import pandas as pd


def dixon_prediction(season, abilities=None, mw=0, timespan=None):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    # Testing Dataset
    test = datasets.dc_dataframe(season=season, abilities=timespan, mw=mw)

    hprob = np.zeros(len(test))
    aprob = np.zeros(len(test))

    # Iterate through each game to determine the winner and prediction
    for row in test.itertuples():

        if abilities is not None:
            hmean = abilities[row.home]['att'] * abilities[row.away]['def'] * abilities['home']
            amean = abilities[row.away]['att'] * abilities[row.home]['def']
        else:
            hmean = row.hmean
            amean = row.amean

        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(hmean, amean)

    # Actual winners and predictions
    winners = np.where(test.hpts > test.apts, test.home, test.away)
    predictions = np.where(hprob > aprob, test.home, test.away)
    outcomes = pd.DataFrame({'winner': winners, 'prediction': predictions, 'date': test.date,
                             'prob': np.maximum(hprob, aprob), 'correct': np.equal(winners, predictions)})

    return outcomes


def best_player_prediction(season, penalty=0.25):
    """
    Prediction using Dixon Coles team abilities and a penalty if a team is missing their best player

    :param season: NBA Season
    :param penalty: Best player penalty
    :return: Accuracy, Betting stats
    """

    # datasets
    games = datasets.dc_dataframe(season=season, abilities=True, bet=True)
    players = datasets.player_dataframe(season=season, teams=True)

    # Team penalties
    games['hpen'], games['apen'] = pu.best_player_penalty(players, games, penalty)

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    # Team Probabilities
    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean * row.hpen, row.amean * row.apen)

    winners = np.where(games.hpts > games.apts, games.home, games.away)
    prediction = np.where(hprob > aprob, games.home, games.away)
    correct = np.equal(winners, prediction)

    roi, profit = pu.betting(hprob, aprob, games)

    return sum(correct) / len(games), np.array(roi), np.array(profit)


def star_player_prediction(season, percentile=84):
    """
    Prediction using Dixon Coles team abilities and a penalty if a team is a missing a star player

    :param season: NBA season
    :param penalty: Star player penalty
    :return: Accuracy, Betting stats
    """

    # Datasets
    games = datasets.dc_dataframe(season=season, abilities=True, bet=True)
    players = datasets.player_dataframe(season=season, teams=True)

    # Team Penalties
    games['hpen'], games['apen'] = pu.star_player_penalty(players, games, percentile)

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    # Team probabilities
    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean * row.hpen, row.amean * row.apen)

    winners = np.where(games.hpts > games.apts, games.home, games.away)
    prediction = np.where(hprob > aprob, games.home, games.away)
    correct = np.equal(winners, prediction)

    roi, profit = pu.betting(hprob, aprob, games)

    return sum(correct) / len(games), np.array(roi), np.array(profit)
