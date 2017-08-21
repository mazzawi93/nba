import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson, beta
from models import prediction_utils as pu

from db import mongo_utils, process_utils, datasets
import pandas as pd


def dixon_coles(params, games, nteams, week, time):
    """
    This is the likelihood function for the Dixon Coles model adapted for basketball.

    :param timespan: Weeks or days
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


def dixon_robinson(params, games, nteams, model):
    """
    Likelihood function for the Dixon and Robinson model

    Currently reworking it to work with full vectors instead of iterations.  Only have model 1 for now.

    :param params: Dixon-Robinson Model Parameters
    :param games: DataFrame of games
    :param nteams: Number of teams
    :param model: Dixon Robinson model
    :return:
    """
    hmean = params[games['home']] * params[games['away'] + nteams] * params[nteams * 2]
    amean = params[games['away']] * params[games['home'] + nteams]

    home_like = 0
    away_like = 0

    if model > 1:

        hpts = games['hpts'] - games['home1'] - games['home2'] - games['home3'] - games['home4']
        apts = games['apts'] - games['away1'] - games['away2'] - games['away3'] - games['away4']

        for i in range(1, 5):
            home_like += np.dot(poisson.logpmf(games['hpts'], hmean * params[nteams * 2 + i]), games['home' + str(i)])
            away_like += np.dot(poisson.logpmf(games['apts'], amean * params[nteams * 2 + i]), games['away' + str(i)])

        home_like += np.dot(poisson.logpmf(games['hpts'], hmean), hpts)
        away_like += np.dot(poisson.logpmf(games['apts'], amean), apts)
    else:
        home_like += np.dot(poisson.logpmf(games['hpts'], hmean), games['hpts'])
        away_like += np.dot(poisson.logpmf(games['apts'], amean), games['apts'])

    total_like = np.sum(poisson.logpmf(games['hpts'], hmean)) + np.sum(poisson.logpmf(games['apts'], amean))

    return -(home_like + away_like - total_like)



def player_beta(params, pts, tpts, weeks, week_num, time):
    """
    Likelihood function to determine player beta distribution parameters

    :return: Likelihood
    """
    likelihood = beta.logpdf(pts / tpts, params[0], params[1])
    weight = np.exp(-time * (week_num - weeks))

    return -np.dot(likelihood, weight)
