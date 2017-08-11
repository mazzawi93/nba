import numpy as np
from scipy.stats import beta

from db import datasets, mongo_utils
from models import prediction_utils as pu
import pandas as pd


def dixon_prediction(season, abilities=None):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    # Testing Dataset
    test = datasets.dc_dataframe(season=season, bet=True, abilities=True)

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


def best_player_prediction(season):
    mongo = mongo_utils.MongoDB()

    # datasets
    test = datasets.dc_dataframe(season=season, abilities=True, bet=True)
    players = datasets.player_dataframe(season=season, teams=True)

    test['hbest'] = 1
    test['abest'] = 1

    for week, stats in players.groupby('week'):

        bp = mongo.find_one('team_best_player', {'week': int(week)}, {'_id': 0, 'week': 0})

        for _id, game in stats.groupby('game'):

            home = np.where(game.phome, game.player, '')
            away = np.where(game.phome, '', game.player)

            index = test[test._id == _id].index[0]

            home_team = game.home.unique()[0]
            away_team = game.away.unique()[0]

            if bp[home_team]['player1'] not in home:
                test.loc[index, 'hbest'] = test.loc[index, 'hbest'] - (bp[home_team]['mean1']) / 4

            if bp[away_team]['player1'] not in away:
                test.loc[index, 'abest'] = test.loc[index, 'abest'] - (bp[away_team]['mean1']) / 4

            if bp[home_team]['player2'] not in home:
                test.loc[index, 'hbest'] = test.loc[index, 'hbest'] - (bp[home_team]['mean2']) / 4

            if bp[away_team]['player2'] not in away:
                test.loc[index, 'abest'] = test.loc[index, 'abest'] - (bp[away_team]['mean2']) / 4

    hprob, aprob = np.zeros(len(test)), np.zeros(len(test))

    for row in test.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean * row.hbest, row.amean * row.abest)

    winners = np.where(test.hpts > test.apts, test.home, test.away)
    prediction = np.where(hprob > aprob, test.home, test.away)
    correct = np.equal(winners, prediction)

    roi, profit = pu.betting(hprob, aprob, test)

    return sum(correct) / len(test), np.array(roi), np.array(profit)


def star_player_prediction(season):
    mongo = mongo_utils.MongoDB()

    # datasets
    test = datasets.dc_dataframe(season=season, abilities=True, bet=True)
    players = datasets.player_dataframe(season=season, teams=True)

    test['hbest'] = 1
    test['abest'] = 1

    for week, stats in players.groupby('week'):

        bp = mongo.find_one('best_player_position', {'week': int(week)}, {'_id': 0, 'week': 0})

        df = pd.DataFrame(bp['85'])

        for _id, game in stats.groupby('game'):

            homep = np.where(game.phome, game.player, '')
            awayp = np.where(game.phome, '', game.player)

            home_team = game.home.unique()[0]
            away_team = game.away.unique()[0]

            index = test[test._id == _id].index[0]

            home = df[df['team'] == home_team]
            away = df[df['team'] == away_team]

            for row in home.itertuples():
                if row.player not in homep:
                    test.loc[index, 'hbest'] = test.loc[index, 'hbest'] - row.mean / 5

            for row in away.itertuples():
                if row.player not in awayp:
                    test.loc[index, 'abest'] = test.loc[index, 'abest'] - row.mean / 5

    hprob, aprob = np.zeros(len(test)), np.zeros(len(test))

    for row in test.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.hmean * row.hbest, row.amean * row.abest)

    winners = np.where(test.hpts > test.apts, test.home, test.away)
    prediction = np.where(hprob > aprob, test.home, test.away)
    correct = np.equal(winners, prediction)

    roi, profit = pu.betting(hprob, aprob, test)

    return sum(correct) / len(test), np.array(roi), np.array(profit)
