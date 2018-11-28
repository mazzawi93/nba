import time

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson

from scrape import team_scraper, scrape_utils

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
        for year in range(2019, 2020):
            # Game Logs
            team_scraper.season_game_logs(team, year)

            # Starting Lineups
            #player_scraper.get_starting_lineups(team, year)

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
        self.abilities = datasets.team_abilities(mw)

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

    def game_predictions(self, seasons=None):
        """
        Game predictions for the 2015 to 2017 NBA seasons using the weekly abilities
        """

        games = datasets.game_results(season=seasons)
        self.predictions = game_prediction.dixon_prediction(games, mw=self.mw)

    def betting_dataframe(self, r, sportsbooks = None):

        if self.predictions is None:
            self.game_predictions()

        odds = datasets.betting_df(sportsbook = sportsbooks)
        betting = self.predictions.merge(odds, on = '_id', how = 'inner')

        hbp = 1/betting['home_odds']
        abp = 1/betting['away_odds']

        take = hbp + abp

        hbp = hbp / take
        abp = abp / take

        betting['home_r'] = betting['hprob'] / hbp
        betting['away_r'] = betting['aprob'] / abp

        r = 1.4

        betting.head()
        betting['home_bet'] = np.where(betting['home_r'] >= r, 10, 0)
        betting['away_bet'] = np.where(betting['away_r'] >= r, 10, 0)

        betting['home_revenue'] = np.where((betting['home_pts'] > betting['away_pts']), betting['home_bet'] * betting['home_odds'], 0)

        betting['away_revenue'] = np.where((betting['away_pts'] > betting['home_pts']), betting['away_bet'] * betting['away_odds'], 0)

        betting['profit'] = betting['home_revenue'] - betting['home_bet'] + betting['away_revenue'] - betting['away_bet']

        return betting


    def betting_r_one_per_sportsbook(self,
                                     sportsbooks = ['SportsInteraction', 'Pinnacle Sports', 'bet365'],
                                     to_file = False,
                                     file_name = 'betting.xlsx'
                                     below_r = 2.05,
                                     starting_bankroll = 2000,
                                     fluc_allowance = 1.5,
                                     risk_tolerance = 10):

        if self.predictions is None:
            self.game_predictions()

        odds = datasets.betting_df(sportsbook = sportsbooks)
        betting = self.predictions.merge(odds, on = '_id', how = 'inner')

        pd_list = []

        if to_file:
            writer = pd.ExcelWriter(file_name)

        for year, games in betting.groupby('season'):

            hbp = 1/games['home_odds']
            abp = 1/games['away_odds']

            take = hbp + abp

            games['hbp'] = hbp / take
            games['abp'] = abp / take

            r = np.arange(1, below_r, 0.05)

            dollars_bet = []
            games_bet = []
            profit = []
            roi = []

            for value in r:

                value = round(value, 2)
                bankroll = starting_bankroll
                bet_total = 0
                game_count = 0

                for game_id, game in games.groupby('_id'):

                    home_bet = game.hprob / game.hbp
                    home_bet = np.logical_and(home_bet < below_r, home_bet >= value)

                    away_bet = game.aprob / game.abp
                    away_bet = np.logical_and(away_bet < below_r, away_bet >= value)

                    hbet = home_bet.any()
                    abet = home_bet.any()

                    if hbet:

                        home_amount = 1/(game.home_odds.max() * fluc_allowance * risk_tolerance) * bankroll
                        bet_total += home_amount
                        game_count += 1
                        bankroll = bankroll - home_amount

                    if abet:

                        away_amount = 1/(game.away_odds.max() * fluc_allowance * risk_tolerance) * bankroll
                        bet_total += away_amount
                        bankroll = bankroll - away_amount
                        game_count += 1

                    if hbet:
                        if((game.home_pts > game.away_pts).any()):
                            bankroll = bankroll + (home_amount * game.home_odds.max())

                    if abet:
                        if((game.away_pts > game.home_pts).any()):
                            bankroll = bankroll + (away_amount * game.away_odds.max())

                dollars_bet.append(bet_total)
                profit.append(bankroll - starting_bankroll)

                if(bet_total == 0):
                    roi.append(0)
                else:
                    roi.append((bankroll - starting_bankroll)/bet_total * 100)
                games_bet.append(game_count)

            b = pd.DataFrame({'r': r, 'roi': roi, 'profit': profit, 'dollars_bet': dollars_bet, 'games_bet': games_bet})
            pd_list.append(b)

            if to_file:
                b.to_excel(writer, str(year), index = False)

        if to_file:
            writer.save()

        return pd_list


    def betting_r_pattern_specific_sportsbook(self,
                                              sportsbooks = None,
                                              to_file = False,
                                              below_r = 2.05,
                                              fluc_allowance = 1.5,
                                              risk_tolerance = 100,
                                              starting_bankroll = 2000):

        if self.predictions is None:
            self.game_predictions()

        odds = datasets.betting_df(sportsbook = sportsbooks)
        betting = self.predictions.merge(odds, on = '_id', how = 'inner')

        pd_list = []

        for sportsbook, games in betting.groupby('sportsbook'):

            writer = pd.ExcelWriter(sportsbook + '.xlsx')

            for year, games2 in games.groupby('season'):

                hbp = 1/games2['home_odds']
                abp = 1/games2['away_odds']

                take = hbp + abp

                games2['hbp'] = hbp / take
                games2['abp'] = abp / take

                r = np.arange(1, below_r, 0.05)

                dollars_bet = []
                games_bet = []
                profit = []
                roi = []

                for value in r:

                    value = round(value, 2)
                    bankroll = starting_bankroll
                    bet_total = 0
                    g = 0

                    for game, row in games2.iterrows():

                        home_bet = row.hprob / row.hbp
                        home_bet = home_bet < below_r and home_bet >= value

                        away_bet = row.aprob / row.abp
                        away_bet = away_bet < below_r and away_bet >= value

                        if home_bet:
                            home_amount = 1/(row.home_odds * fluc_allowance * risk_tolerance)*bankroll
                            bet_total += home_amount
                            g += 1
                            bankroll = bankroll - home_amount

                        if away_bet:
                            away_amount = 1/(row.away_odds * fluc_allowance * risk_tolerance)*bankroll
                            bet_total += away_amount
                            bankroll = bankroll - away_amount
                            g += 1

                        if home_bet:
                            if(row.home_pts > row.away_pts):
                                bankroll = bankroll + (home_amount * row.home_odds)

                        if away_bet:
                            if(row.away_pts > row.home_pts):
                                bankroll = bankroll + (away_amount * row.away_odds)

                    dollars_bet.append(bet_total)
                    profit.append(bankroll - starting_bankroll)

                    if bet_total == 0:
                        roi.append(0)
                    else:
                        roi.append((bankroll - starting_bankroll)/bet_total * 100)
                    games_bet.append(g)
                b = pd.DataFrame({'r': r, 'roi': roi, 'profit': profit, 'dollars_bet': dollars_bet, 'games_bet': games_bet})
                pd_list.append(b)
                b.to_excel(writer, str(year), index = False)
            if to_file:
                writer.save()

        return pd_list
