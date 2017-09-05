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


def player_penalty(games, mw, pen_factor, star_factor=85, star=False):
    """
    Determine team penalties if they are missing their best player

    :param games: NBA Games
    :param mw: Match weighting
    :param pen_factor: Multiply the beta mean by this factor
    :return: Team penalties
    """

    # MongoDB
    m = mongo.Mongo()

    # Penalties are multiplied with dixon coles abilities, so no penalty is equal to one
    hpenalty = np.full(len(games), 1, dtype=float)
    apenalty = np.full(len(games), 1, dtype=float)

    # Each week will have different best players as they are determined by recent games
    for week, stats in games.groupby('week'):

        # Best Players
        bp = m.find_one('player_beta', {'week': int(week), 'mw': mw}, {'_id': 0, 'week': 0, 'mw': 0})
        bp = pd.DataFrame.from_dict(bp, 'index')
        bp.dropna(inplace=True)
        bp['beta'] = np.nan_to_num(beta.mean(bp.a, bp.b))

        for row in stats.itertuples():

            try:

                home = bp[bp.team == row.home]

                if star:
                    home_star = home[home.beta >= np.percentile(bp.beta, star_factor)]

                    for p in home_star.index:
                        if p not in row.hplayers:
                            hpenalty[row.Index] = hpenalty[row.Index] - home.loc[p].beta * pen_factor
                else:
                    home_best = home.beta.argmax()

                    if home_best not in row.hplayers:
                        hpenalty[row.Index] = hpenalty[row.Index] - home.loc[home_best].beta * pen_factor

            except ValueError:
                pass

            try:
                away = bp[bp.team == row.away]

                if star:
                    away_star = away[away.beta >= np.percentile(bp.beta, star_factor)]

                    for p in away_star.index:
                        if p not in row.aplayers:
                            apenalty[row.Index] = apenalty[row.Index] - away.loc[p].beta * pen_factor
                else:
                    away_best = away.beta.argmax()

                    if away_best not in row.aplayers:
                        apenalty[row.Index] = apenalty[row.Index] - away.loc[away_best].beta * pen_factor
            except ValueError:
                pass

    return hpenalty, apenalty
