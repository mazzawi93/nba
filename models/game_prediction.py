import numpy as np
from scipy.stats import beta

from db import datasets, mongo_utils
from models import prediction_utils as pu
import pandas as pd


def dixon_prediction(season, abilities=None, xi=0.0):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    # Testing Dataset
    test = datasets.dc_dataframe(season=season, bet=True, abilities=True, xi=xi)

    # ngames = np.zeros(100)
    # ncorrect = np.zeros(100)

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

    # Determine correct predictions
    correct = np.equal(winners, predictions)

    # if correct:
    #    ncorrect[int(predict_prob * 100)] += 1
    # ngames[int(predict_prob * 100)] += 1

    roi, profit = pu.betting(hprob, aprob, test)

    return sum(correct) / len(test), np.array(roi), np.array(profit)


def player_poisson_prediction(season):
    """
    Prediction using Dixon Coles team abilities and player poisson means

    :param season: NBA season
    :return: Accuracy, betting return on investment
    """

    # Datasets
    test = datasets.dc_dataframe(season=season, abilities=True, bet=True)
    players = datasets.player_dataframe(season=season, poisson=True)

    test['hpm'] = 0
    test['apm'] = 0

    for _id, stats in players.groupby('game'):
        # Poisson means by summing up the player ones
        hp = np.sum(np.where(stats['phome'], stats['mean'], 0))
        ap = np.sum(np.where(stats['phome'], 0, stats['mean']))

        index = test[test._id == _id].index[0]

        # Set the values in the game dataset
        test.loc[index, 'hpm'] = hp
        test.loc[index, 'apm'] = ap

    hprob, aprob = np.zeros(len(test)), np.zeros(len(test))

    for row in test.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hpm, row.apm)

    winners = np.where(test.hpts > test.apts, test.home, test.away)
    prediction = np.where(hprob > aprob, test.home, test.away)

    correct = np.equal(winners, prediction)

    roi, profit = pu.betting(hprob, aprob, test)

    return sum(correct) / len(test), np.array(roi), np.array(profit)


def player_beta_prediction(season):
    """
    Prediction using Dixon Coles Team abilities and player beta distributions

    :param season: NBA Season
    :return: Accuracy, betting return on investment
    """

    # Datasets
    test = datasets.dc_dataframe(season=season, abilities=True, bet=True)
    players = datasets.player_dataframe(season=season, beta=True)

    test['hbeta'] = 0
    test['abeta'] = 0

    # Get beta means for each game
    for _id, stats in players.groupby('game'):
        hbeta = np.sum(np.nan_to_num(np.where(stats.phome, beta.mean(stats.a, stats.b), 0)))
        abeta = np.sum(np.nan_to_num(np.where(stats.phome, 0, beta.mean(stats.a, stats.b))))

        index = test[test._id == _id].index[0]

        test.loc[index, 'hbeta'] = hbeta
        test.loc[index, 'abeta'] = abeta

    hprob, aprob = np.zeros(len(test)), np.zeros(len(test))

    for row in test.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean * row.hbeta, row.amean * row.abeta)

    winners = np.where(test.hpts > test.apts, test.home, test.away)
    prediction = np.where(hprob > aprob, test.home, test.away)
    correct = np.equal(winners, prediction)

    roi, profit = pu.betting(hprob, aprob, test)

    return sum(correct) / len(test), roi, profit


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
