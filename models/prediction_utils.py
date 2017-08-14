import numpy as np
from scipy.stats import poisson
from db import mongo_utils
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


def best_player_penalty(players, games, pen_factor):
    """
    Determine team penalties if they are missing their best player

    :param players: NBA Players
    :param games: NBA Games
    :param pen_factor: Multiply the beta mean by this factor
    :return: Team penalties
    """

    # MongoDB
    mongo = mongo_utils.MongoDB()

    # Penalties are multiplied with dixon coles abilities, so no penalty is equal to one
    hpenalty = np.full(len(games), 1, dtype=float)
    apenalty = np.full(len(games), 1, dtype=float)

    # Each week will have different best players as they are determined by recent games
    for week, stats in players.groupby('week'):

        # Best Players
        bp = mongo.find_one('best_player_teams', {'week': int(week)}, {'_id': 0, 'week': 0})

        # Set the penalties for each game
        for _id, game in stats.groupby('game'):

            home = np.where(game.phome, game.player, '')
            away = np.where(game.phome, '', game.player)

            index = games[games._id == _id].index[0]

            home_team = game.home.unique()[0]
            away_team = game.away.unique()[0]

            if bp[home_team]['player'] not in home:
                hpenalty[index] = hpenalty[index] - (bp[home_team]['mean']) * pen_factor

            if bp[away_team]['player'] not in away:
                apenalty[index] = apenalty[index] - (bp[away_team]['mean']) * pen_factor

    return hpenalty, apenalty


def star_player_penalty(players, games, star_factor):
    """
    Determine team penalties if missing a 'star' player

    :param players: NBA Players
    :param games: NBA Games
    :return: Team penalties
    """

    # MongoDB
    mongo = mongo_utils.MongoDB()

    # Penalties are multiplied with dixon coles abilities, so no penalty is equal to one
    hpenalty = np.full(len(games), 1, dtype=float)
    apenalty = np.full(len(games), 1, dtype=float)

    # Each week will have different star players as they are determined by recent games
    for week, stats in players.groupby('week'):

        # Star Players
        bp = mongo.find_one('best_player_position', {'week': int(week)}, {'_id': 0, 'week': 0})

        # Get the 85th percentile
        df = pd.DataFrame(bp[str(star_factor)])

        # Set penalties for each game
        for _id, game in stats.groupby('game'):

            homep = np.where(game.phome, game.player, '')
            awayp = np.where(game.phome, '', game.player)

            home_team = game.home.unique()[0]
            away_team = game.away.unique()[0]

            index = games[games._id == _id].index[0]

            home = df[df['team'] == home_team]
            away = df[df['team'] == away_team]

            for row in home.itertuples():
                if row.player not in homep:
                    hpenalty[index] = hpenalty[index] - row.mean * 0.17

            for row in away.itertuples():
                if row.player not in awayp:
                    apenalty[index] = apenalty[index] - row.mean * 0.17

    return hpenalty, apenalty


def time_score(xi):
    games = datasets.dc_dataframe(season=[2015, 2016, 2017], abilities=True, xi=xi)

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = determine_probabilities(row.hmean, row.amean)

    hw = np.where(games.hpts > games.apts, True, False)

    return np.sum(np.log(hprob[hw])) + np.sum(np.log(hprob[np.invert(hw)]))


def player_penalty_score(penalty):
    """
    Determine the log score of a penalty factor

    :param pen_factor: Penalty
    :return: Log Score
    """
    games = datasets.dc_dataframe(season=[2015, 2016, 2017], abilities=True)
    players = datasets.player_dataframe(season=[2015, 2016, 2017], teams=True)

    games['hpen'], games['apen'] = best_player_penalty(players, games, pen_factor)

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = determine_probabilities(row.hmean * row.hpen, row.amean * row.apen)

    hw = np.where(games.hpts > games.apts, True, False)

    return np.sum(np.log(hprob[hw])) + np.sum(np.log(hprob[np.invert(hw)]))


def star_penalty_score(percentile):
    """
    Determine the log score of a penalty factor

    :param pen_factor: Penalty
    :return: Log Score
    """
    games = datasets.dc_dataframe(season=[2015, 2016, 2017], abilities=True)
    players = datasets.player_dataframe(season=[2015, 2016, 2017], teams=True)

    games['hpen'], games['apen'] = star_player_penalty(players, games, percentile)

    hprob, aprob = np.zeros(len(games)), np.zeros(len(games))

    for row in games.itertuples():
        hprob[row.Index], aprob[row.Index] = determine_probabilities(row.hmean * row.hpen, row.amean * row.apen)

    hw = np.where(games.hpts > games.apts, True, False)

    return np.sum(np.log(hprob[hw])) + np.sum(np.log(hprob[np.invert(hw)]))
