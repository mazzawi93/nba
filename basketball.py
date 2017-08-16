import time

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from db import datasets, mongo_utils, process_utils
from models import nba_models as nba
from models import game_prediction
from models import prediction_utils as pu


class Basketball:
    """
    Basketball class used to manipulate team abilities and simulate upcoming seasons
    """

    def __init__(self):
        """
        Initialize Basketball class by setting class variables
        """

        self.nteams = 30
        self.teams = process_utils.name_teams(False, 30)

        self.con = [{'type': 'eq', 'fun': pu.attack_constraint, 'args': (100, self.nteams,)},
                    {'type': 'eq', 'fun': pu.defense_constraint, 'args': (1, self.nteams,)}]

        self.abilities = None

    def test_model(self, season=None):
        """
        Test the optimized model against a testing set and apply a betting strategy

        :param season: NBA Season(s)
        :return: Number of correct predictions and number of games by percentage
        """

        # If it is nba data we are working with get current season, else create a testing set with the same
        # parameters as the training set
        if season is None:
            season = 2017

        outcomes = game_prediction.dixon_prediction(season, self.abilities)

        return outcomes


class DixonColes(Basketball):
    """
    Subclass for the Dixon and Coles model which uses the full time scores of each match.
    """

    def __init__(self, season, mw=0):
        """
        Initialize DixonColes instance.

        :param season: NBA Season(s)
        :param mw: Recent match weight
        """

        super().__init__()

        self.dataset = datasets.dc_dataframe(self.teams, season, mw=mw)

        # Initial Guess for the minimization
        a0 = pu.initial_guess(0, self.nteams)

        # Minimize the likelihood function
        self.opt = minimize(nba.dixon_coles, x0=a0,
                            args=(self.dataset, self.nteams, self.dataset['week'].max() + 28, mw),
                            constraints=self.con, method='SLSQP')

        # SciPy minimization requires a numpy array for all abilities, so convert them to readable dict
        self.abilities = pu.convert_abilities(self.opt.x, 0, self.teams)


class DixonRobinson(Basketball):
    """
    Subclass for the Dixon and Robinson model which uses the time each point was scored rather than only full time
    scores.
    """

    def __init__(self, season, model=1):
        """
        Initialize DixonRobinson instance.

        :param model: Dixon and Robinson model (1 to 4)
        :param season: NBA Season(s)
        """

        super().__init__()

        self.dataset = datasets.dr_dataframe(model, self.teams, season)

        # Initial Guess for the minimization
        a0 = pu.initial_guess(model, self.nteams)

        # Minimize the likelihood function
        self.opt = minimize(nba.dixon_robinson, x0=a0, args=(self.dataset, self.nteams, model),
                            constraints=self.con)

        # SciPy minimization requires a numpy array for all abilities, so convert them to readable dict
        self.abilities = pu.convert_abilities(self.opt.x, model, self.teams)


class DynamicDixonColes(Basketball):
    def __init__(self, mw=0.0394, timespan='week'):
        """
        Computes the team abilities for every week by combining the datasets and using the time value,
        starting with the 2013 season as the base values for teams.
        """

        if timespan != 'day' and timespan != 'week':
            raise ValueError('Time must be day or week')

        super().__init__()

        # MongoDB
        self.mongo = mongo_utils.MongoDB()

        self.mw = mw
        self.predictions = None
        self.timespan = timespan

        if self.mongo.count(timespan + '_dixon', {'mw': mw}) == 0:
            print('Team abilities don\'t exist, generating them now...')
            self.dynamic_abilities()

        # Retrieve abilities from db
        self.abilities = self.mongo.find(timespan + '_dixon', {'mw': mw}, {'mw': 0, '_id': 0})

    def dynamic_abilities(self):

        self.mongo.remove(self.timespan + '_dixon', {'mw': self.mw})

        # Datasets
        start_df = datasets.dc_dataframe(self.teams, 2013)
        rest_df = datasets.dc_dataframe(self.teams, [2014, 2015, 2016, 2017])

        # Initial Guess
        a0 = pu.initial_guess(0, self.nteams)

        # Group them by time span (weeks or days)
        span_df = rest_df.groupby(self.timespan)

        # Recalculate the Dixon Coles parameters every week after adding the previous week to the dataset
        for span, stats in span_df:

            # Get team parameters for the current week
            opt = minimize(nba.dixon_coles, x0=a0, args=(start_df, self.nteams, span, self.mw, self.timespan),
                           constraints=self.con, method='SLSQP')

            abilities = pu.convert_abilities(opt.x, 0, self.teams)

            # Store weekly abilities
            abilities[self.timespan] = int(span)
            abilities['mw'] = self.mw

            self.mongo.insert(self.timespan + '_dixon', abilities)

            # Append this week to the database
            start_df = start_df.append(stats, ignore_index=True)

    def game_predictions(self):

        self.predictions = game_prediction.dixon_prediction([2015, 2016, 2017], mw=self.mw, timespan=self.timespan)


class Players(DynamicDixonColes):

    def __init__(self, mw=0.0394, timespan='week'):

        super().__init__(mw=0.0394, timespan=timespan)

        if self.mongo.count('player_beta', {'mw': mw}) == 0:
            print('Player distributions don\'t exist, generating them now...')
            self.player_weekly_abilities()

            # Retrieve abilities from db
            self.abilities = self.mongo.find('player_beta', {'mw': mw}, {'mw': 0, '_id': 0})

    def player_weekly_abilities(self):

        # Delete the abilities in the database if existing
        self.mongo.remove('player_beta', {'mw': mw})

        # Datasets
        start_df = datasets.player_dataframe([2013], teams=True, position=True)
        rest_df = datasets.player_dataframe([2014, 2015, 2016, 2017], teams=True, position=True)

        # Group them by weeks
        weeks_df = rest_df.groupby('week')

        for week, stats in weeks_df:

            players_df = start_df.groupby('player')
            players = {'week': int(week), 'mw': self.mw}

            for name, games in players_df:

                team_pts = np.where(games.phome, games.hpts, games.apts)
                a0 = np.array([games.pts.mean(), (team_pts - games.pts).mean()])

                opt = minimize(player_beta, x0=a0, args=(games.pts, team_pts, games.week, int(week), self.mw))

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

            self.mongo.insert('player_beta', players)

            start_df = start_df.append(stats, ignore_index=True)