import numpy as np
from scipy.stats import poisson


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


def betting(hprob, aprob, df):
    """
    Determine the return on investment from betting odds

    :param hprob: Probability of home team winning
    :param aprob: Probability of away team winning
    :param df: Dataframe containing odds and results
    :return: Return on investment
    """
    r = np.arange(1, 2, 0.05)

    hbp = 1 / df['hbet']
    abp = 1 / df['abet']

    # Bookmakers 'take
    take = hbp + abp

    # Rescale odds so they add to 1
    hbp = hbp / take
    abp = abp / take

    roi = []
    profit = []

    for value in r:
        # Bet on ome and away teams
        bet_home = hprob / hbp > value
        bet_away = aprob / abp > value

        hp = np.dot(bet_home.astype(int), np.where(df['hpts'] > df['apts'], df['hbet'], 0))
        ap = np.dot(bet_away.astype(int), np.where(df['apts'] > df['hpts'], df['abet'], 0))

        nbets = sum(bet_home) + sum(bet_away)
        roi.append((np.sum(hp) + np.sum(ap) - nbets) / nbets * 100)
        profit.append(np.sum(hp) + np.sum(ap) - nbets)

    return roi, profit


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