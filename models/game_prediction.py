import numpy as np
from scipy.stats import beta
from scipy.stats import bernoulli

from db import datasets, mongo_utils
from models import prediction_utils as pu
import pandas as pd


def dixon_prediction(season, abilities=None, mw=0, players=False, star=False, bernoulli=False):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    games = datasets.dc_dataframe(season=season, abilities=True, mw=mw, players=players)

    hprob = np.zeros(len(games))
    aprob = np.zeros(len(games))

    if players:
        games['hpen'], games['apen'] = pu.player_penalty(games, mw, 0.17, star)
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


    if bernoulli:
        home_win = np.random.binomial(1000, hprob)
        print(home_win)
        predictions = np.where(home_win >= 500, games.home, games.away)
    else:
        predictions = np.where(hprob > aprob, games.home, games.away)

    outcomes = pd.DataFrame({'winner': winners, 'prediction': predictions, 'month': games.date.dt.month,
                             'prob': np.maximum(hprob, aprob), 'correct': np.equal(winners, predictions),
                             'season': games.season})

    return outcomes