import math
import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
import time_stat as ts

teams = ['ATL', 'BOS', 'BRK', 'CHO', 'CHI', 'CLE', 'DAL', 'DEN', 'DET', 'GSW', 'HOU', 'IND', 'LAC', 'LAL', 'MEM', 'MIA',
         'MIL', 'MIN', 'NOP', 'NYK', 'OKC', 'ORL', 'PHI', 'PHO', 'POR', 'SAC', 'SAS', 'TOR', 'UTA', 'WAS']


def norm_alphas(params):
    return sum(params[:30]) / 30 - 100


def likelihood(abilities, matches):
    total = 0
    for game in matches:
        hteam, ateam = game[0], game[2]
        hpts, apts = game[1], game[3]

        hi, ai = 0, 0
        for i in [i for i, x in enumerate(teams) if x == hteam]:
            hi = i

        for i in [i for i, x in enumerate(teams) if x == ateam]:
            ai = i

        hmean = abilities[60] * abilities[hi] * abilities[ai + 30]
        amean = abilities[hi + 30] * abilities[ai]

        # print("%s %s" % (hmean, amean))
        # print("%s %s" % (hpts, apts))
        # print("%s %s" % (poisson.pmf(hmean, hpts), poisson.pmf(amean, apts)))
        # print("")

        try:
            homea = math.log(poisson.pmf(hpts, hmean))
        except ValueError:
            homea = 0

        try:
            awaya = math.log(poisson.pmf(apts, amean))
        except ValueError:
            awaya = 0
        total += homea + awaya

    return -total

def log(num):
    try:
        return math.log(num)
    except ValueError:
        return 0


def goal_likelihood(abilities, matches):
    total = 0
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
                like += log(abilities[hi]) + log(abilities[ai + 30]) + log(abilities[60])
            else:
                like += log(abilities[hi + 30]) + log(abilities[ai])

        total += like

    return -total


def write_stats(stat, file):
    g = open(file, 'w')
    g.write('%s\t%s\t%s\n' % ('Team', 'Attack', 'Defense'))

    for i in range(0, 30):
        team = teams[i]
        att = format(float(stat[i]), '.2f')
        defense = format(float(stat[i + 30]), '.2f')

        g.write('%s\t%s\t%s\n' % (team, att, defense))

    g.write('Home Advantage\t%s' % stat[60])
    g.close()


tor = ts.match_point_times([2016])
tor = tor.as_matrix()

ab = np.random.rand(61)

con = {'type': 'eq', 'fun': norm_alphas}

opt = minimize(likelihood, x0=ab, args=tor, constraints=con)

print(opt)
write_stats(opt.x, 'stats_no_constraint.txt')