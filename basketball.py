import time

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from db import datasets, mongo, process_utils
from models import nba_models as nba
from models import game_prediction
from models import prediction_utils as pu
from scipy.stats import beta


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

        self.dataset = datasets.game_dataset(self.teams, season, mw=mw)

        # Initial Guess for the minimization
        a0 = pu.initial_guess(0, self.nteams)

        # Minimize the likelihood function
        self.opt = minimize(nba.dixon_coles, x0=a0,
                            args=(self.dataset, self.nteams, self.dataset['week'].max() + 28, mw),
                            constraints=self.con, method='SLSQP')

        # SciPy minimization requires a numpy array for all abilities, so convert them to readable dict
        self.abilities = pu.convert_abilities(self.opt.x, 0, self.teams)


class DynamicDixonColes(Basketball):
    def __init__(self, mw=0.0394):
        """
        Computes the team abilities for every week by combining the datasets and using the match weight value,
        starting with the 2013 season as the base values for teams.
        """

        super().__init__()

        # MongoDB
        self.mongo = mongo.Mongo()

        self.mw = mw
        self.predictions = None
        self.bets = None

        if self.mongo.count('dixon_team', {'mw': mw}) == 0:
            print('Team abilities don\'t exist, generating them now...')
            self.dynamic_abilities()

        # Retrieve abilities from db
        self.abilities = self.mongo.find('dixon_team', {'mw': mw}, {'mw': 0, '_id': 0})

    def dynamic_abilities(self):
        """
        Find the weekly abilities of teams and store them in the database.
        """

        self.mongo.remove('dixon_team', {'mw': self.mw})

        # Datasets
        start_df = datasets.game_dataset(self.teams, [2013, 2014])
        rest_df = datasets.game_dataset(self.teams, [2015, 2016, 2017])

        # Initial Guess
        a0 = pu.initial_guess(0, self.nteams)

        # Recalculate the Dixon Coles parameters every week after adding the previous week to the dataset
        for week, stats in rest_df.groupby('week'):
            # Get team parameters for the current week
            opt = minimize(nba.dixon_coles, x0=a0, args=(start_df, self.nteams, week, self.mw),
                           constraints=self.con, method='SLSQP')

            abilities = pu.convert_abilities(opt.x, 0, self.teams)

            # Store weekly abilities
            abilities['week'] = int(week)
            abilities['mw'] = self.mw

            self.mongo.insert('dixon_team', abilities)

            # Append this week to the database
            start_df = start_df.append(stats, ignore_index=True)

    def game_predictions(self):
        """
        Game predictions for the 2015 to 2017 NBA seasons using the weekly abilities
        """

        self.predictions = game_prediction.dixon_prediction([2015, 2016, 2017], mw=self.mw)

    def betting(self):
        """
        Determine the return on investment from betting odds

        :return: Return on investment
        """

        if self.predictions is None:
            self.game_predictions()

        games = datasets.game_dataset(season=[2015, 2016, 2017], bet=True)

        r = np.arange(1, 3, 0.05)

        hbp = 1 / games['hbet']
        abp = 1 / games['abet']

        # Bookmakers 'take
        take = hbp + abp

        # Rescale odds so they add to 1
        hbp = hbp / take
        abp = abp / take

        roi = []
        profit = []
        n = []

        for value in r:
            # Bet on ome and away teams
            bet_home = hprob / hbp > value
            bet_away = aprob / abp > value

            hp = np.dot(bet_home.astype(int), np.where(games['hpts'] > games['apts'], games['hbet'], 0))
            ap = np.dot(bet_away.astype(int), np.where(games['apts'] > games['hpts'], games['abet'], 0))

            nbets = sum(bet_home) + sum(bet_away)
            roi.append((np.sum(hp) + np.sum(ap) - nbets) / nbets * 100)
            profit.append(np.sum(hp) + np.sum(ap) - nbets)
            n.append(nbets)

        return pd.DataFrame({'r': r, 'roi': np.array(roi), 'profit': np.array(profit), 'nbets': np.array(n)})

    def team_progression(self, team):
        """
        Generate a team's offensive and defensive progression over the weeks

        :param team: NBA team or 'home' for the home court advantage
        :return: Attack and defense abilities for team
        """

        if team not in self.teams and team != 'home':
            raise ValueError('Team does not exist.')

        weeks = self.mongo.find('dixon_team', {'mw': self.mw}, {team: 1})

        attack = []
        defence = []

        for week in weeks:

            if team == 'home':
                attack.append(week[team])
            else:
                attack.append(week[team]['att'])
                defence.append(week[team]['def'])

        return np.array(attack), np.array(defence)


class PlayerPoisson(DynamicDixonColes):
    def __init__(self, mw=0.0394):
        super().__init__(mw)

        if self.mongo.count('player_poisson', {'mw': self.mw}) == 0:
            print('Player distributions don\'t exist, generating them now...')
            self.player_weekly_abilities()

    def player_weekly_abilities(self):

        # Delete the abilities in the database if existing
        self.mongo.remove('player_poisson', {'mw': self.mw})

        # Datasets
        start_df = datasets.player_dataframe([2013, 2014])
        rest_df = datasets.player_dataframe([2015, 2016, 2017])

        # Group them by weeks
        weeks_df = rest_df.groupby('week')

        for week, stats in weeks_df:

            players = {'week': int(week), 'mw': self.mw}

            for name, games in start_df.groupby('player'):

                opt = minimize(nba.player_poisson, x0=games.pts.mean(), args=(games.pts, games.week, int(week), self.mw))

                if opt.x[0] < 0:
                    opt.x[0] = 0

                players[str(name)] = opt.x[0]

            self.mongo.insert('player_poisson', players)

            start_df = start_df.append(stats, ignore_index=True)

    def game_predictions(self):
        self.predictions = game_prediction.poisson_prediction([2015, 2016, 2017], mw=self.mw)

    def player_progression(self, player):

        weeks = self.mongo.find('player_poisson', {'mw': self.mw}, {player: 1, '_id': 0})
        means = []

        for week in weeks:
            means.append(week[player])

        return np.array(means)


class Players(DynamicDixonColes):
    def __init__(self, mw=0.0394):
        """
            Computes the player abilities for every week by combining the datasets and using the match weight value,
            starting with the 2013 season as the base values for Players.
        """

        super().__init__(mw=mw)

        if self.mongo.count('player_beta', {'mw': self.mw}) == 0:
            print('Player distributions don\'t exist, generating them now...')
            self.player_weekly_abilities()

    def player_weekly_abilities(self):
        """
        Generate weekly player abilities.
        """

        # Delete the abilities in the database if existing
        self.mongo.remove('player_beta', {'mw': self.mw})

        # Datasets
        start_df = datasets.player_dataframe([2013, 2014], teams=True, position=True)
        rest_df = datasets.player_dataframe([2015, 2016, 2017], teams=True, position=True)

        # Group them by weeks
        weeks_df = rest_df.groupby('week')

        # If a player has played a few games in 2013 and retired, they will be carried through the entire optimisation.
        # Need to find a way to remove players out of the league but leave players who are injured.
        for week, stats in weeks_df:

            players = {'week': int(week), 'mw': self.mw}

            for name, games in start_df.groupby('player'):

                team_pts = np.where(games.phome, games.hpts, games.apts)
                a0 = np.array([games.pts.mean(), (team_pts - games.pts).mean()])

                opt = minimize(nba.player_beta, x0=a0, args=(games.pts, team_pts, games.week, int(week), self.mw))

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

    def game_predictions(self, penalty=0.17, star=False, star_factor=85, bet=False):

        self.predictions = game_prediction.dixon_prediction([2015, 2016, 2017], mw=self.mw, penalty=penalty, players=True, star=star,
                                                            star_factor=star_factor)

    def player_progression(self, player):

        weeks = self.mongo.find('player_beta', {'mw': self.mw}, {player: 1, '_id': 0})
        means = []

        for week in weeks:
            print(week)
            means.append(beta.mean(week[player]['a'], week[player]['b']))

        return np.array(means)

    def betting(self):

        if self.predictions is None:
            self.predictions = game_prediction.dixon_prediction([2015, 2016, 2017], mw=self.mw)

        super().betting()