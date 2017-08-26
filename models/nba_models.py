import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson, beta
from models import prediction_utils as pu

from db import mongo_utils, process_utils, datasets
import pandas as pd


def dixon_coles(params, games, nteams, week, time):
    """
    This is the likelihood function for the Dixon Coles model adapted for basketball.

    :param time: Time decay factor (Bigger number results in higher weighting for recent matches)
    :param week: Current week of the simulation
    :param nteams: Number of teams in dataset
    :param params: Dixon-Coles Model Parameters
    :param games: DataFrame of games
    :return: Log Likelihood from the Dixon-Coles Model
    """

    hmean = params[games['home']] * params[games['away'] + nteams] * params[nteams * 2]
    amean = params[games['away']] * params[games['home'] + nteams]

    likelihood = poisson.logpmf(games['hpts'], hmean) + poisson.logpmf(games['apts'], amean)
    weight = np.exp(-time * (week - games['week']))

    return -np.dot(likelihood, weight)


def player_beta(params, pts, tpts, weeks, week_num, time):
    """
    Likelihood function to determine player beta distribution parameters

    :return: Likelihood
    """
    likelihood = beta.logpdf(pts / tpts, params[0], params[1])
    weight = np.exp(-time * (week_num - weeks))

    return -np.dot(likelihood, weight)
