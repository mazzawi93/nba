import numpy as np
from scipy.stats import beta
from scipy.stats import bernoulli

from db import datasets, mongo
from models import prediction_utils as pu
import pandas as pd


def dixon_prediction(season, mw=0.044):
    """
    Dixon Coles or Robinson game prediction based off the team probabilities.

    The team with the highest probability of winning is chosen as the winner

    :return: Accuracy, betting return on investment
    """

    games = datasets.game_results(season=2018)
    abilities, home = datasets.team_abilities(mw = 0.044)

    games = games.merge(home, how = 'left')
    games = games.merge(abilities, left_on = ['week', 'home_team'], right_on = ['week', 'team']).merge(abilities, left_on = ['week', 'away_team'], right_on = ['week', 'team'])
    games = games.rename(columns = {'attack_x': 'home_attack', 'attack_y': 'away_attack', 'defence_x': 'home_defence', 'defence_y': 'away_defence'}).drop(['team_x', 'team_y'], axis = 1)

    games['home_mean'] = games['home_attack'] * games['away_defence'] * games['home']
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

    outcomes = outcomes.drop(['home', 'home_attack', 'home_defence', 'away_attack', 'away_defence', 'week'], axis = 1)
    outcomes['hprob'] = hprob
    outcomes['aprob'] = aprob

    return outcomes
