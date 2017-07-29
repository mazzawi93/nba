from db import datasets
from scipy.stats import poisson
from db import mongo_utils
import numpy as np


def determine_probabilities(hmean, amean):
    """
    Determine the probabilities of 2 teams winning a game
    :param hmean: Home team poisson mean
    :param amean: Away team poisson mean
    :return: Probabilities of home and away team
    """

    hprob, aprob = 0, 0

    # The probability for the home team is the sum of the poisson probabilities when h > a and
    # vice versa for the away team
    for h in range(60, 140):
        for a in range(60, 140):

            if h > a:
                hprob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))
            elif h < a:
                aprob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))

    return hprob, aprob


def dixon_prediction(display=False):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Number of correct predictions and number of games by percentage
    """

    # Mongo DB
    mongo = mongo_utils.MongoDB()

    # Testing Dataset
    test = datasets.dc_dataframe(season=2017)

    ngames = np.zeros(100)
    ncorrect = np.zeros(100)

    date = None
    abilities = None

    # Iterate through each game to determine the winner and prediction
    for row in test.itertuples():

        if row.date != date:
            date = row.date
            abilities = mongo.find_one('dixon', {'min_date': {'$lte': date}, 'max_date': {'$gte': date}})

        hmean = abilities[row.home]['att'] * abilities[row.away]['def'] * abilities['home']
        amean = abilities[row.away]['att'] * abilities[row.home]['def']

        hprob, aprob = determine_probabilities(hmean, amean)

        if row.hpts > row.apts:
            winner = row.home
        else:
            winner = row.away

        if hprob > aprob:
            predict = row.home
            predict_prob = hprob
        else:
            predict = row.away
            predict_prob = aprob

        if winner == predict:
            correct = True
        else:
            correct = False

        if correct:
            ncorrect[int(predict_prob * 100)] += 1
        ngames[int(predict_prob * 100)] += 1

        if display:
            print('Game: %d\t\tPredicted: %s\t\tWinner: %s' % (row.Index, predict, winner))

    return ncorrect, ngames
