from scipy.stats import beta
import numpy as np
from scipy.stats import poisson
from db import mongo
from db import datasets
import pandas as pd


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


def attack_constraint(params, constraint, nteams):
    """
    Attack parameter constraint for the likelihood functions

    :param constraint: The mean for attack
    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - constraint
    """

    return sum(params[:nteams]) / nteams - constraint


def defense_constraint(params, constraint, nteams):
    """
    Attack parameter constraint for the likelihood functions

    :param constraint: Mean for defense
    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[nteams:nteams * 2]) / nteams - constraint


def initial_guess(model, nteams):
    """
    Create an initial guess for the minimization function
    :param nteams: Number of teams
    :param model: The model implemented (0: DC, 1: Base DR model, 2: Time Parameters, 3: winning/losing)
    :return: Numpy array of team abilities (Attack, Defense) and Home Advantage and other factors
    """

    # Attack and Defence parameters
    att = np.full((1, nteams), 100, dtype=float)
    defense = np.full((1, nteams), 1, dtype=float)
    teams = np.append(att, defense)

    # The time parameters are added to the model
    if model == 2:
        params = np.full((1, 5), 1.05, dtype=float)
    else:
        params = np.full((1, nteams), 1.0, dtype=float)

    return np.append(teams, params)


def convert_abilities(opt, model, teams):
    """
    Convert the numpy abilities array into a more usable dict
    :param teams: Team names
    :param opt: Abilities from optimization
    :param model: Model number determines which parameters are included (0 is Dixon Coles)
    """
    abilities = {'att': {}, 'def': {}, 'home_adv': {}}

    i = 0

    nteams = len(teams)

    # Attack and defense
    for team in teams:
        abilities['att'][team] = opt[i]
        abilities['def'][team] = opt[i + nteams]
        abilities['home_adv'][team] = opt[i + nteams + nteams]
        i += 1

    return abilities


def home_accuracy(group):
    home_correct = sum((group.home_pts > group.away_pts) & (group.hprob > group.aprob))
    num_guesses = sum(group.hprob > group.aprob)

    return home_correct/num_guesses

def away_accuracy(group):
    home_correct = sum((group.away_pts > group.home_pts) & (group.aprob > group.hprob))
    num_guesses = sum(group.aprob > group.hprob)

    return home_correct/num_guesses


def win_accuracy(group):
    home_correct = sum((group.home_pts > group.away_pts) & (group.hprob > group.aprob))
    away_correct = sum((group.away_pts > group.home_pts) & (group.aprob > group.hprob))

    return (home_correct + away_correct)/len(group)
