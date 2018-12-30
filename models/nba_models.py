""" This module contains functions to model basketball teams. """

import numpy as np
from scipy.stats import poisson
from scipy.stats import beta


def dixon_coles(params, games, nteams, date, day_span, decay):
    """
    This is the likelihood function for the Dixon Coles model adapted for basketball.

    Args:
        params: Dixon-Coles model parameters
        games: DataFrame of historical results
        nteams: Number of teams in dataset
        week: Current week of the simulation
        decay: Time decay factor (Bigger number results in higher weighting for recent matches)

    Returns:
        The Log Likelihood from the Dixon-Coles Model with the passed set of parameters
    """

    hmean = params[games['home_team']] \
            * params[games['away_team'] + nteams] \
            * params[games['home_team'] + nteams + nteams]

    amean = params[games['away_team']] \
            * params[games['home_team'] + nteams]

    likelihood = poisson.logpmf(games['home_pts'], hmean) + poisson.logpmf(games['away_pts'], amean)
    weight = np.exp(-decay * np.ceil(((date - games['date']).dt.days) / day_span))

    return -np.dot(likelihood, weight)


def player_beta(params, games, date, day_span, decay):
    """
    Likelihood function to determine player beta distribution parameters
    :return: Likelihood
    """

    likelihood = beta.logpdf(games['pts'] / games['team_pts'], params[0], params[1])
    weight = np.exp(-decay * np.ceil(((date - games['date']).dt.days) / day_span))

    return -np.dot(likelihood, weight)
