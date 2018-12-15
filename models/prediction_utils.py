from scipy.stats import beta
import numpy as np
from scipy.stats import poisson
from db import mongo
from db import datasets
import pandas as pd

def determine_probabilities_sample(row):

    home = np.random.poisson(row.home_mean, 10000)
    away = np.random.poisson(row.away_mean, 10000)

    hprob = sum(home > away)/len(home)
    aprob = sum(away > home)/len(away)

    return pd.Series([hprob, aprob])

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


def convert_abilities(opt, teams):
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


def bet_season(games, low_r, high_r, **kwargs):

    # Optimal Betting Strategy
    fluc_allowance = kwargs.get('fluc_allowance', 1.5)
    risk_tolerance = kwargs.get('risk_tolerance', 10)
    starting_bankroll = kwargs.get('starting_bankroll', 2000)

    lr = round(low_r, 2)

    # R upper limit
    hr = round(high_r, 2)

    stats = {'season': '-'.join(str(e) for e in n), 'low_r': lr, 'high_r': hr}

    # Bet Total
    stats['home_total'] = 0
    stats['away_total'] = 0

    # Games Bet
    stats['home_count'] = 0
    stats['away_count'] = 0

    # Bet Revenue
    stats['home_revenue'] = 0
    stats['away_revenue'] = 0

    bankroll = starting_bankroll

    # Filter the games we're not gonna bet on
    games['home_bet'] = np.logical_and(games.home_R < hr, games.home_R >= lr)
    games['away_bet'] = np.logical_and(games.away_R < hr, games.away_R >= lr)

    games = games.loc[(games.home_bet) | (games.away_bet)]

    for game_id, game in games.groupby('_id'):

        if kwargs.get('any', True):
            hbet = home_bet.any()
            abet = away_bet.any()
        else:
            hbet = home_bet.all()
            abet = away_bet.all()

        if hbet:

            home_amount = 1/(game.home_odds.max() * fluc_allowance * risk_tolerance) * bankroll
            bankroll = bankroll - home_amount

            # Home stats
            stats['home_total'] += home_amount
            stats['home_count'] += 1


        if abet:

            away_amount = 1/(game.away_odds.max() * fluc_allowance * risk_tolerance) * bankroll
            bankroll = bankroll - away_amount

            # Away stats
            stats['away_total'] += away_amount
            stats['away_count'] += 1

        if hbet:
            if((game.home_pts > game.away_pts).any()):
                bankroll = bankroll + (home_amount * game.home_odds.max())
                stats['home_revenue'] += (home_amount * game.home_odds.max())

        if abet:
            if((game.away_pts > game.home_pts).any()):
                bankroll = bankroll + (away_amount * game.away_odds.max())
                stats['away_revenue'] += (away_amount * game.away_odds.max())

    stats['home_profit'] = stats['home_revenue'] - stats['home_total']
    stats['away_profit'] = stats['away_revenue'] - stats['away_total']

    stats['bet_total'] = stats['home_total'] + stats['away_total']
    stats['profit'] = bankroll - starting_bankroll

    try:
        stats['home_rob'] = ((stats['home_revenue'] - stats['home_total'])/stats['home_total'] * 100)
    except ZeroDivisionError:
        stats['home_rob'] = 0

    try:
        stats['away_rob'] = ((stats['away_revenue'] - stats['away_total'])/stats['away_total'] * 100)
    except ZeroDivisionError:
        stats['away_rob'] = 0

    try:
        stats['roi'] = ((bankroll - starting_bankroll)/starting_bankroll * 100)
    except ZeroDivisionError:
        stats['roi'] = 0

    try:
        stats['rob'] = ((bankroll - starting_bankroll)/stats['bet_total'] * 100)
    except ZeroDivisionError:
        stats['rob'] = 0

    return pd.DataFrame(stats, index = [0])
