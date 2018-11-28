import numpy as np
import pandas as pd

from models import prediction_utils as pu
from db import datasets


def dixon_prediction(dataset, mw=0.044):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    games = dataset.copy()
    abilities = datasets.team_abilities(mw = 0.044)

    games = games.merge(abilities, left_on = ['week', 'home_team'], right_on = ['week', 'team']).merge(abilities, left_on = ['week', 'away_team'], right_on = ['week', 'team'])
    games = games.rename(columns = {'attack_x': 'home_attack', 'attack_y': 'away_attack', 'defence_x': 'home_defence', 'defence_y': 'away_defence', 'home_adv_x': 'home_adv'}).drop(['team_x', 'team_y', 'home_adv_y'], axis = 1)

    games['home_mean'] = games['home_attack'] * games['away_defence'] * games['home_adv']
    games['away_mean'] = games['away_attack'] * games['home_defence']

    # Win probabilities
    hprob = np.zeros(len(games))
    aprob = np.zeros(len(games))

    # Iterate through each game to determine the winner and prediction
    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.home_mean, row.away_mean)

    # Scale odds so they add to 1
    scale = 1 / (hprob + aprob)
    hprob = hprob * scale
    aprob = aprob * scale

    games = games[['_id', 'season', 'date', 'home_team', 'home_pts', 'away_pts', 'away_team']]
    games['hprob'] = hprob
    games['aprob'] = aprob

    return games.sort_values('date')
