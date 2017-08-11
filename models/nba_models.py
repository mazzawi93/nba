import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson, beta
from models import prediction_utils as pu

from db import mongo_utils, process_utils, datasets
import pandas as pd


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
    Computes the team abilities for every week by combining the datasets and using the time value,
    starting with the 2013 season as the base values for teams.
    """

    # MongoDB
    mongo = mongo_utils.MongoDB()

    teams = process_utils.name_teams(False, 30)

    # Datasets
    start_df = datasets.dc_dataframe(teams, 2013)
    rest_df = datasets.dc_dataframe(teams, [2014, 2015, 2016, 2017])

    # Dixon Constraint
    con = [{'type': 'eq', 'fun': pu.attack_constraint, 'args': (100, 30,)},
           {'type': 'eq', 'fun': pu.defense_constraint, 'args': (1, 30,)}]

    # Initial Guess
    a0 = pu.initial_guess(0, 30)

    # Group them by weeks
    weeks_df = rest_df.groupby('week')

    # Recalculate the Dixon Coles parameters every week after adding the previous week to the dataset
    for week, stats in weeks_df:
        # Get team parameters for the current week
        opt = minimize(dixon_coles, x0=a0, args=(start_df, 30, week, 0.024),
                       constraints=con, method='SLSQP')
        abilities = pu.convert_abilities(opt.x, 0, teams)

        # Store weekly abilities
        abilities['min_date'] = stats.date.min()
        abilities['max_date'] = stats.date.max()
        abilities['week'] = int(week)
        mongo.insert('dixon', abilities)

        # Append this week to the database
        start_df = start_df.append(stats, ignore_index=True)


def player_poisson(params, games, week, time):
    """
    Likelihood function to determine player poisson mean

    :return: Likelihood
    """

    likelihood = poisson.logpmf(games['pts'], params[0])
    weight = np.exp(-time * (week - games['week']))

    return -np.dot(likelihood, weight)


def dynamic_poisson():
    """
    Compute weekly player poisson means.

    """

    # Mongo DB
    mongo = mongo_utils.MongoDB()

    # Datasets
    start_df = datasets.player_dataframe(2013)
    rest_df = datasets.player_dataframe([2014, 2015, 2016, 2017])

    # Group them by weeks
    weeks_df = rest_df.groupby('week')

    for week, stats in weeks_df:

        players_df = start_df.groupby('player')
        players = {'week': int(week)}
        for name, games in players_df:

            if games.pts.mean() == 0:
                players[str(name)] = 0
            else:
                opt = minimize(player_poisson, x0=games.pts.mean(), args=(games, week, 0.024))

                if opt.x[0] < 0:
                    opt.x[0] = 0

                players[str(name)] = opt.x[0]

        mongo.insert('player_poisson', players)

        # Append this week to the dataframe
        start_df = start_df.append(stats, ignore_index=True)


def player_beta(params, pts, tpts, weeks, week_num, time):
    """
    Likelihood function to determine player beta distribution parameters

    :return: Likelihood
    """
    likelihood = beta.logpdf(pts / tpts, params[0], params[1])
    weight = np.exp(-time * (week_num - weeks))

    return -np.dot(likelihood, weight)


def dynamic_beta():
    """
    Compute weekly player beta parameters

    """

    # Mongo DB
    mongo = mongo_utils.MongoDB()

    # Datasets
    start_df = datasets.player_dataframe([2013], teams=True, position=True)
    rest_df = datasets.player_dataframe([2014, 2015, 2016, 2017], teams=True, position=True)

    # Group them by weeks
    weeks_df = rest_df.groupby('week')

    for week, stats in weeks_df:

        players_df = start_df.groupby('player')
        players = {'week': int(week)}



        for name, games in players_df:

            team_pts = np.where(games.phome, games.hpts, games.apts)
            a0 = np.array([games.pts.mean(), (team_pts - games.pts).mean()])

            opt = minimize(player_beta, x0=a0, args=(games.pts, team_pts, games.week, int(week), 0.024))

            if opt.status == 2:
                players[str(name)] = {'a': a0[0], 'b': a0[1]}
            else:
                players[str(name)] = {'a': opt.x[0], 'b': opt.x[1]}

            try:
                teams = stats.groupby('player').get_group(name)
                teams = teams[teams.week == week]
                teams = np.unique(np.where(teams.phome, teams.home, teams.away))[0]

                players[str(name)]['team'] = teams

                position = stats.groupby('player').get_group(name)
                position = position.pos.unique()[0]
                players[str(name)]['position'] = position
            except KeyError:
                pass

        mongo.insert('player_beta', players)

        start_df = start_df.append(stats, ignore_index=True)


def find_best_players():
    """
    Find each teams best player going into a game
    """

    # Mongo
    mongo = mongo_utils.MongoDB()

    weeks = mongo.find('player_beta')

    for players in weeks:

        del players['_id']
        week = players['week']
        del players['week']

        df = pd.DataFrame.from_dict(players, 'index')


        players = {'week': int(week)}
        positions = {'week': int(week), '95': [], '90': [], '85': [], '80': [], '75': []}

        for pos, stats in df.groupby('position'):

            bm = np.nan_to_num(beta.mean(stats.a, stats.b))


            for num in zip(*np.where(bm > np.percentile(bm, 95))):
                positions['95'].append(
                    {'player': stats.index[num], 'mean': bm[num], 'team': stats.loc[stats.index[num], 'team']})

            for num in zip(*np.where(bm > np.percentile(bm, 90))):
                positions['90'].append(
                    {'player': stats.index[num], 'mean': bm[num], 'team': stats.loc[stats.index[num], 'team']})

            for num in zip(*np.where(bm > np.percentile(bm, 85))):
                positions['85'].append(
                    {'player': stats.index[num], 'mean': bm[num], 'team': stats.loc[stats.index[num], 'team']})

            for num in zip(*np.where(bm > np.percentile(bm, 80))):
                positions['80'].append(
                    {'player': stats.index[num], 'mean': bm[num], 'team': stats.loc[stats.index[num], 'team']})

            for num in zip(*np.where(bm > np.percentile(bm, 75))):
                positions['75'].append(
                    {'player': stats.index[num], 'mean': bm[num], 'team': stats.loc[stats.index[num], 'team']})


        for team, stats in df.groupby('team'):

            bm = np.nan_to_num(beta.mean(stats.a, stats.b))

            players[team] = {'player1': str(stats.index[bm.argmax()]), 'mean1': bm.max()}

            bm = np.delete(bm, bm.argmax())

            players[team]['player2'] = str(stats.index[bm.argmax()])
            players[team]['mean2'] = bm.max()





        mongo.insert('best_player_teams', players)
        mongo.insert('best_player_position', positions)

