import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize

from db import mongo_utils, process_utils, datasets


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


def initial_guess(model, nteams):
    """
    Create an initial guess for the minimization function
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
        params = np.full((1, 1), 1.05, dtype=float)

    return np.append(teams, params)


def convert_abilities(opt, model, teams):
    """
    Convert the numpy abilities array into a more usable dict
    :param opt: Abilities from optimization
    :param model: Model number determines which parameters are included (0 is Dixon Coles)
    """
    abilities = {'model': model}

    i = 0

    nteams = len(teams)

    # Attack and defense
    for team in teams:
        abilities[team] = {
            'att': opt[i],
            'def': opt[i + nteams]
        }
        i += 1

    # Home Advantage
    abilities['home'] = opt[nteams * 2]

    # Time parameters
    if model >= 2:
        abilities['time'] = {
            'q1': opt[nteams * 2 + 1],
            'q2': opt[nteams * 2 + 2],
            'q3': opt[nteams * 2 + 3],
            'q4': opt[nteams * 2 + 4]
        }

    return abilities


def dixon_coles(params, games, nteams, week, time):
    """
    This is the likelihood function for the Dixon Coles model adapted for basketball.

    :param time: Time decay factor (Bigger number results in higher weighting for recent matches)
    :param week: Current week of the simulation
    :param nteams: Number of teams in dataset
    :param params: Dixon-Coles Model Paramters
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


def dynamic_dixon_coles():
    """
    Computer the team abilities for every week by combining the datasets and using the time value,
    starting with the 2013 season as the base values for teams.
    """

    # MongoDB
    mongo = mongo_utils.MongoDB()

    teams = process_utils.name_teams(False, 30)

    # Datasets
    start_df = datasets.dc_dataframe(teams, 2013)
    rest_df = datasets.dc_dataframe(teams, [2014, 2015, 2016, 2017])

    # Dixon Constraint
    con = [{'type': 'eq', 'fun': attack_constraint, 'args': (100, 30,)},
           {'type': 'eq', 'fun': defense_constraint, 'args': (1, 30,)}]

    # Initial Guess
    a0 = initial_guess(0, 30)

    # Group them by weeks
    weeks_df = rest_df.groupby('week')

    # Recalculate the Dixon Coles parameters every week after adding the previous week to the dataset
    for t in weeks_df.groups:

        opt = minimize(dixon_coles, x0=a0, args=(start_df, 30, t, 0.024),
                       constraints=con, method='SLSQP')

        abilities = convert_abilities(opt.x, 0, teams)

        week = weeks_df.get_group(t)
        date = set()

        for row in week.itertuples():
            date.add(row.date.to_pydatetime())
            start_df.append(week, ignore_index=True, in_place=True)

        abilities['min_date'] = min(date)
        abilities['max_date'] = max(date)
        mongo.insert('dixon', abilities)


def player_dixon_coles(params, games, week, time):

    likelihood = poisson.logpmf(games['ppts'], params[0])
    weight = np.exp(-time * (week - games['week']))

    return -np.dot(likelihood, weight)