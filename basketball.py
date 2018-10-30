import time

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from scrape import team_scraper

from db import datasets, mongo, process_utils
from models import nba_models as nba
from models import game_prediction
from models import prediction_utils as pu
from scipy.stats import beta

def scrape_all():
    """ Scrape all the information from basketball-reference and oddsportal for betting odds."""

    # Scrape team information by season
    for team in scrape_utils.team_names():

        team_scraper.team_season_stats(team)

        # Each season
        for year in range(2013, 2020):

            # Game Logs
            team_scraper.season_game_logs(team, year)

            # Starting Lineups
            player_scraper.get_starting_lineups(team, year)

    # Init mongo to get game IDS for box score scraping
    m = mongo.Mongo()

    # Game Information (Box Score and Play by Play)
    for year in range(2018, 2020):
        for game in m.find('game_log', {'season': year}, {'_id': 1}):
            team_scraper.play_by_play(game['_id'])
            player_scraper.player_box_score(game['_id'])
            print(game['_id'])


    # Get player information
    for player in scrape_utils.get_active_players():
        print(player)
        player_scraper.player_per_game(player)

    # Get betting lines (By Year) need from 2014
    for year in range(2013, 2019):
        team_scraper.betting_lines(year)



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

        self.dataset = datasets.game_results(season, self.teams)

        # Initial Guess for the minimization
        a0 = pu.initial_guess(0, self.nteams)

        # Minimize the likelihood function
        self.opt = minimize(nba.dixon_coles, x0=a0,
                            args=(self.dataset, self.nteams, self.dataset['week'].max() + 28, mw),
                            constraints=self.con, method='SLSQP')

        # SciPy minimization requires a numpy array for all abilities, so convert them to readable dict
        self.abilities = pu.convert_abilities(self.opt.x, 0, self.teams)


class DynamicDixonColes(Basketball):
    def __init__(self, mw=0.044):
        """
        Computes the team abilities for every week by combining the datasets and using the match weight value,
        starting with the 2013 season as the base values for teams.
        """

        super().__init__()

        # MongoDB
        self.mongo = mongo.Mongo()

        self.mw = mw
        self.predictions = None

        if self.mongo.count('dixon_team', {'mw': mw}) == 0:
            print('Team abilities don\'t exist, generating them now...')
            self.dynamic_abilities()

        # Retrieve abilities from db
        self.abilities, self.home_advantage = datasets.team_abilities(mw)

    def dynamic_abilities(self):
        """
        Find the weekly abilities of teams and store them in the database.
        """

        self.mongo.remove('dixon_team', {'mw': self.mw})

        # Datasets
        start_df = datasets.game_results([2013, 2014], self.teams)
        rest_df = datasets.game_results([2015, 2016, 2017, 2018, 2019], self.teams)

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

    def game_predictions(self, seasons):
        """
        Game predictions for the 2015 to 2017 NBA seasons using the weekly abilities
        """

        self.predictions = game_prediction.dixon_prediction(seasons, mw=self.mw)



    # TODO: Update
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
