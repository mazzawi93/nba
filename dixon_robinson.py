import math
import string

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

import time_stat as ts


def attack_constraint(params, nteams):
    """
    Attack parameter constraint for the likelihood functions
    The Mean of the attack parameters must equal 100

    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[:nteams]) / nteams - 100


def initial_guess(num):
    """
    Create an initial guess for the minimization function
    :param num: The number of teams
    :return: Numpy array of team abilities (Attack, Defense) and Home Advantage
    """

    att = np.full((1, num), 100)
    dh = np.full((1, num + 1), 1)
    return np.append(att, dh)


def dixon_coles(abilities, matches, teams):
    total = 0

    num = len(teams)

    for game in matches:
        hteam, ateam = game[0], game[2]
        hpts, apts = game[1], game[3]

        hi, ai = 0, 0
        for i in [i for i, x in enumerate(teams) if x == hteam]:
            hi = i

        for i in [i for i, x in enumerate(teams) if x == ateam]:
            ai = i

        hmean = abilities[num * 2] * abilities[hi] * abilities[ai + num]
        amean = abilities[hi + num] * abilities[ai]

        total += poisson.logpmf(hpts, hmean) + poisson.logpmf(apts, amean)

    return -total


def log(num):
    try:
        return math.log(num)
    except ValueError:
        return 0


def goal_likelihood(abilities, matches, teams):
    total = 0

    # Number of teams
    num = len(teams)

    for game in matches:

        home = game[0]
        away = game[2]

        hi, ai = 0, 0
        for i in [i for i, x in enumerate(teams) if x == home]:
            hi = i

        for i in [i for i, x in enumerate(teams) if x == away]:
            ai = i

        like = 0
        for point in game[4]:

            if point['home'] == 1:

                mean = abilities[hi] * abilities[ai + num] * abilities[num * 2]

            else:
                mean = abilities[hi + num] * abilities[ai]

            like += log(mean)

        total += like

    return -total


def write_stats(stat, file, num):
    g = open(file, 'w')
    g.write('%s\t%s\t%s\n' % ('Team', 'Attack', 'Defense'))

    for i in range(0, num):
        att = format(float(stat[i]), '.2f')
        defense = format(float(stat[i + num]), '.2f')

        g.write('%s\t%s\n' % (att, defense))

    g.write('Home Advantage\t%s' % stat[num * 2])
    g.close()


def dixon_coles_test_set(data, num):
    # Initial Guess
    abilities = initial_guess(num)

    # Team Names
    teams = []
    for i in range(num):
        teams.append(string.ascii_uppercase[i])

    # Likelihood constraint
    con = {'type': 'eq', 'fun': attack_constraint, 'args': (num,)}

    opt = minimize(dixon_coles, x0=abilities, args=(data, teams), constraints=con)

    return opt


def print_abilities(ab):
    num = int((len(ab) - 1) / 2)

    att = ab[:num]
    defend = ab[num:num * 2]
    home = ab[len(ab) - 1]

    for x in range(0, num):
        print('%s\t%s' % (att[x], defend[x]))

    print('Home Advantage: %s' % home)


def nba_dixon_coles(season):
    """
    Apply the dixon coles model to an NBA season to find the attack and defense parameters for each team
    as well as the home court advantage
    :param season: NBA Season
    :return:
    """

    # NBA Teams
    teams = ['ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM',
             'MIA', 'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHO', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS']

    # Initial Guess for the minimization
    att = np.full((1, len(teams)), 10)
    dh = np.full((1, len(teams) + 1), 1)
    ab = np.append(att, dh)

    # NBA Season Data
    nba = ts.match_point_times([season])
    nba = nba.drop('time', axis=1)
    nba = nba.as_matrix()

    # Minimize Constraint
    con = {'type': 'eq', 'fun': attack_constraint, 'args': (len(teams),)}

    # Minimize the likelihood function
    opt = minimize(dixon_coles, x0=ab, args=(nba, teams), constraints=con)

    return opt
