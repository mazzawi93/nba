import string

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

import db.time_stat as ts


def attack_constraint(params, nteams):
    """
    Attack parameter constraint for the likelihood functions
    The Mean of the attack parameters must equal 100

    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[:nteams]) / nteams - 100


def initial_guess(num, model=None):
    """
    Create an initial guess for the minimization function
    :param model:
    :param num: The number of teams
    :return: Numpy array of team abilities (Attack, Defense) and Home Advantage
    """

    att = np.full((1, num), 100)

    if model == 0:
        dh = np.full((1, num + 1), 1)
    # The time parameters are added to the model
    elif model == 1:
        dh = np.full((1, num + 5), 1)
    else:
        dh = np.full((1, num + 1), 1)

    return np.append(att, dh)


def dixon_coles(abilities, matches, teams):
    """
    This is the likelihood function for the Dixon Coles model.
    :param abilities:
    :param matches:
    :param teams:
    :return: Likelihood
    """
    total = 0

    num = len(teams)

    for game in matches:
        hteam, ateam = game[0], game[2]
        hpts, apts = game[1], game[3]

        # Determine ability indexes
        hi, ai = 0, 0
        for i in [i for i, x in enumerate(teams) if x == hteam]:
            hi = i

        for i in [i for i, x in enumerate(teams) if x == ateam]:
            ai = i

        # Home and Away Poisson intensities
        hmean = abilities[num * 2] * abilities[hi] * abilities[ai + num]
        amean = abilities[hi + num] * abilities[ai]

        # Log Likelihood
        total += poisson.logpmf(hpts, hmean) + poisson.logpmf(apts, amean)

    return -total


def dixon_robinson(abilities, matches, teams, model):
    total = 0

    # Number of teams
    num = len(teams)

    for game in matches:

        # Team Names
        home, away = game[0], game[2]

        # Team Indexes for the ability array
        hi, ai = 0, 0
        for i in [i for i, x in enumerate(teams) if x == home]:
            hi = i

        for i in [i for i, x in enumerate(teams) if x == away]:
            ai = i

        like = 0
        hp, ap = 0, 0

        # Iterate through each point scored
        for point in game[4]:

            if model > 1:
                time_stamp = float(point['time'])

                if (11 / 48) < time_stamp <= (12 / 48):
                    time = abilities[num * 2 + 1]
                elif (23 / 48) < time_stamp <= (24 / 48):
                    time = abilities[num * 2 + 2]
                elif (35 / 48) < time_stamp <= (36 / 48):
                    time = abilities[num * 2 + 3]
                elif (47 / 48) < time_stamp <= (48 / 48):
                    time = abilities[num * 2 + 4]
                else:
                    time = 1

            if point['home'] == 0:
                hp += int(point['points'])
                mean = abilities[hi] * abilities[ai + num] * abilities[num * 2]

                like += poisson.logpmf(hp, mean)
            else:
                ap += int(point['points'])
                mean = abilities[hi + num] * abilities[ai]

                like += poisson.logpmf(ap, mean)

            if model > 1:
                like += time
        total += like - poisson.logpmf(hp, (abilities[hi] * abilities[ai + num] * abilities[num * 2])) - poisson.logpmf(
            ap, (abilities[hi + num] * abilities[ai]))

    return -total


def test_set_dixon(data, num, coles, model=None):
    # Initial Guess
    abilities = initial_guess(num, model)

    # Team Names
    teams = []
    for i in range(num):
        teams.append(string.ascii_uppercase[i])

    # Likelihood constraint
    con = {'type': 'eq', 'fun': attack_constraint, 'args': (num,)}

    if coles is True:
        opt = minimize(dixon_coles, x0=abilities, args=(data, teams), constraints=con)
    else:
        opt = minimize(dixon_robinson, x0=abilities, args=(data, teams, model), constraints=con)

    return opt


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


def print_abilities(ab, teams=None):
    num = int((len(ab) - 1) / 2)

    att = ab[:num]
    defend = ab[num:num * 2]
    home = ab[len(ab) - 1]

    if teams is None:
        teams = []
        for i in range(num):
            teams.append(string.ascii_uppercase[i])

    print("\tAttack\tDefense")
    for x in range(0, num):
        print('%s:\t%s\t%s' % (teams[x], format(float(att[x]), '.2f'), format(float(defend[x]), '.2f')))

    print('Home Advantage: %s' % format(float(home), '.2f'))
