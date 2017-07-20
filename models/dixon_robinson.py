import numpy as np
from scipy.stats import poisson


def attack_constraint(params, constraint, nteams):
    """
    Attack parameter constraint for the likelihood functions
    The Mean of the attack parameters must equal 100

    :param constraint: The mean for attack
    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[:nteams]) / nteams - constraint


def defense_constraint(params, constraint, nteams):
    """
    Attack parameter constraint for the likelihood functions
    The Mean of the attack parameters must equal 100

    :param constraint: Mean for defense
    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[nteams:nteams * 2]) / nteams - constraint


def dixon_coles(params, games, week, time):
    """
    This is the likelihood function for the Dixon Coles model adapted for basketball.
    :param params: Dixon-Coles Model Paramters
    :param games: DataFrame of games
    :return: Log Likelihood from the Dixon-Coles Model
    """

    nteams = int(len(params) / 2)

    hmean = params[games['home']] * params[games['away'] + nteams] * params[nteams * 2]
    amean = params[games['away']] * params[games['home'] + nteams]

    likelihood = np.exp(-time * (week-games['week'])) * (poisson.logpmf(games['hpts'], hmean) + poisson.logpmf(games['apts'], amean))

    return -np.sum(likelihood)


def dixon_robinson(params, games, nteams, model):

    hmean = params[games['home']] * params[games['away'] + nteams] * params[nteams * 2]
    amean = params[games['away']] * params[games['home'] + nteams]

    likelihood = poisson.logpmf(games['hpts'], hmean) * games['hpts']
    likelihood += poisson.logpmf(games['apts'], amean) * games['apts']
    likelihood -= poisson.logpmf(games['hpts'], hmean) - poisson.logpmf(games['apts'], amean)

    return -np.sum(likelihood)
