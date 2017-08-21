import numpy as np
from scipy.stats import beta

from db import datasets, mongo_utils
from models import prediction_utils as pu
import pandas as pd


def dixon_prediction(season, abilities=None, mw=0, player_pen=None):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    games = datasets.dc_dataframe(season=season, abilities=True, mw=mw, players=player_pen is not None)

    hprob = np.zeros(len(games))
    aprob = np.zeros(len(games))

    if player_pen is not None:
        games['hpen'], games['apen'] = pu.player_penalty(games, mw, 0.17, player_pen)
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

    # Actual winners and predictions
    winners = np.where(games.hpts > games.apts, games.home, games.away)
    predictions = np.where(hprob > aprob, games.home, games.away)
    outcomes = pd.DataFrame({'winner': winners, 'prediction': predictions, 'month': games.date.dt.month,
                             'prob': np.maximum(hprob, aprob), 'correct': np.equal(winners, predictions),
                             'season': games.season})

    return outcomes
