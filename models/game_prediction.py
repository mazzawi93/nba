from db import datasets
from scipy.stats import poisson
from db import mongo_utils
import numpy as np
import matplotlib.pyplot as plt


def determine_probabilities(hmean, amean):
    """
    Determine the probabilities of 2 teams winning a game
    :param hmean: Home team poisson mean
    :param amean: Away team poisson mean
    :return: Probabilities of home and away team
    """

    # Possible scores
    scores = np.arange(0, 200)

    hprob = np.zeros(len(scores))
    aprob = np.zeros(len(scores))

    # The probability for the home team is the sum of the poisson probabilities when h > a and
    # vice versa for the away team
    for x in scores:
        hprob[x] = np.sum(poisson.pmf(mu=hmean, k=x) * poisson.pmf(mu=amean, k=np.where(scores < x)))
        aprob[x] = np.sum(poisson.pmf(mu=amean, k=x) * poisson.pmf(mu=hmean, k=np.where(scores < x)))

    # Return sum
    return np.sum(hprob), np.sum(aprob)


def dixon_prediction(season, abilities=None, r = 1):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Number of correct predictions and number of games by percentage
    """

    # Mongo DB
    mongo = mongo_utils.MongoDB()

    # Testing Dataset
    test = datasets.dc_dataframe(season=season, bet=True)

    # ngames = np.zeros(100)
    # ncorrect = np.zeros(100)

    date = None

    hprob = np.zeros(len(test))
    aprob = np.zeros(len(test))

    # Iterate through each game to determine the winner and prediction
    for row in test.itertuples():

        if abilities is None:
            if row.date != date:
                date = row.date
                abilities = mongo.find_one('dixon', {'min_date': {'$lte': date}, 'max_date': {'$gte': date}})

        hmean = abilities[row.home]['att'] * abilities[row.away]['def'] * abilities['home']
        amean = abilities[row.away]['att'] * abilities[row.home]['def']

        hprob[row.Index], aprob[row.Index] = determine_probabilities(hmean, amean)

    # Actual winners and predictions
    winners = np.where(test.hpts > test.apts, test.home, test.away)
    predictions = np.where(hprob > aprob, test.home, test.away)

    # Determine correct predictions
    correct = np.equal(winners, predictions)

    # if correct:
    #    ncorrect[int(predict_prob * 100)] += 1
    # ngames[int(predict_prob * 100)] += 1

    # Probabilities set by betting odds
    hbp = 1 / test['hbet']
    abp = 1 / test['abet']

    # Bookmakers 'take'
    take = hbp + abp

    # Rescale odds so they add to 1
    hbp = hbp / take
    abp = abp / take

    # Bet on home and away teams
    bet_home = hprob/hbp > r
    bet_away = aprob/abp > r

    hprofit = np.dot(bet_home.astype(int), np.where(test['hpts'] > test['apts'], test['hbet'], 0))
    aprofit = np.dot(bet_away.astype(int), np.where(test['apts'] > test['hpts'], test['abet'], 0))
    profit = hprofit + aprofit

    exp_return = profit / (sum(bet_home) + sum(bet_away))

    return correct, exp_return
