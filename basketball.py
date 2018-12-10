import time
import datetime
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from db import datasets, mongo, process_utils
from models import nba_models as nba
from models import prediction_utils as pu

from scrape import team_scraper

class nba_model:

    def __init__(self,
                 mw=0.044,
                 att_constraint = 100,
                 def_constraint = 1):

        # Team Information
        self.nteams = 30
        self.teams = process_utils.name_teams(False, 30)

        # MongoDB
        self.mongo = mongo.Mongo()

        # Model parameters
        self.mw = mw
        self.att_constraint = att_constraint
        self.def_constraint = def_constraint

        # Model Outputs
        self.abilities = None
        self.predictions = None

        # Set to the current week
        today = datetime.datetime.now()
        self.week = int(today.strftime("%U")) +  (today.year % 2010 * 52)

        # Train new abilities if they don't exist in the database
        if self.mongo.count('dixon_team', {'mw': self.mw, 'att_constraint': self.att_constraint, 'def_constraint': self.def_constraint}) == 0:
            print('Training All Weeks')
            self.train_all()
        elif self.mongo.count('dixon_team', {'mw': self.mw, 'att_constraint': self.att_constraint, 'def_constraint': self.def_constraint, 'week': self.week}) == 0:
            print('Training Current Week')
            self.train_week()

        # Get all abilities in DF
        self.abilities = datasets.team_abilities(mw, att_constraint, def_constraint)

    def train_all(self, store = True):

        # Get all week numbers from 2015 season
        first_week = datasets.game_results(2015)['week'].min()

        # Generate abilities for each week
        for w in range(first_week, self.week + 1):
            self.train_week(w)


    def train_week(self, week = None):

        # If week is None, then use the current week
        if week is None:
            week = self.week

        # Get all games in DB before given week
        df = datasets.game_results(teams = self.teams, week = week)

        # Remove abilities from DB
        self.mongo.remove('dixon_team', {'mw': self.mw, 'att_constraint': self.att_constraint, 'def_constraint': self.def_constraint, 'week': week})

        # Initial Guess
        a0 = pu.initial_guess(0, self.nteams)

        if self.att_constraint == 'rolling':
            weight = np.exp(-self.mw * (week - start_df['week']))
            att_constraint = np.average(np.append(start_df['home_pts'], start_df['away_pts']), weights = np.append(weight, weight))
        else:
            att_constraint = self.att_constraint

        con = []

        if self.att_constraint is not None:
            con.append({'type': 'eq', 'fun': pu.attack_constraint, 'args': (round(att_constraint), self.nteams,)})

        if self.def_constraint is not None:
            con.append({'type': 'eq', 'fun': pu.defense_constraint, 'args': (round(self.def_constraint), self.nteams,)})

        # Get team parameters for the current week
        opt = minimize(nba.dixon_coles, x0=a0, args=(df, self.nteams, week, self.mw), constraints = [], method='SLSQP')

        abilities = pu.convert_abilities(opt.x, 0, self.teams)

        # Store weekly abilities
        abilities['week'] = int(week)
        abilities['mw'] = self.mw

        # Constraints
        abilities['att_constraint'] = self.att_constraint
        abilities['def_constraint'] = self.def_constraint

        self.mongo.insert('dixon_team', abilities)



    def predict(self, dataset = None, seasons = None, keep_abilities = False):
        """
        Game predictions based on the team.
        """

        # Get the dataset if required
        if dataset is None:
            games = datasets.game_results(season = seasons)
        else:
            games = dataset


        # Merge the team abilities to the results
        games = games.merge(self.abilities, left_on = ['week', 'home_team'], right_on = ['week', 'team']) \
        .merge(self.abilities, left_on = ['week', 'away_team'], right_on = ['week', 'team'])

        # Rename the columns
        games = games.rename(columns = {'attack_x': 'home_attack',
                                        'attack_y': 'away_attack',
                                        'defence_x': 'home_defence',
                                        'defence_y': 'away_defence',
                                        'home_adv_x': 'home_adv'}) \
                      .drop(['team_x', 'team_y', 'home_adv_y'], axis = 1)

        # Compute the means
        games['home_mean'] = games['home_attack'] * games['away_defence'] * games['home_adv']
        games['away_mean'] = games['away_attack'] * games['home_defence']

        # Win probabilities
        hprob = np.zeros(len(games))
        aprob = np.zeros(len(games))

        # Iterate through each game to determine the winner and prediction
        for row in games.itertuples():
            hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.home_mean, row.away_mean)

        # Scale odds so they sum up to 1
        scale = 1 / (hprob + aprob)
        hprob = hprob * scale
        aprob = aprob * scale

        # Drop columns we don't want
        if not keep_abilities:
            games = games.drop(['home_attack', 'home_defence', 'home_adv', 'away_attack', 'away_defence', 'home_mean', 'away_mean'], axis = 1)

        # Add probabilities to DF
        games['hprob'] = hprob
        games['aprob'] = aprob

        # Try to sort by date, but if date doesn't exist it doesn't matter
        try:
            games = games.sort_values('date').reset_index()
        except KeyError:
            pass

        return games.reset_index()


    def games_to_bet(self,
                     predictions = None,
                     sportsbooks = None,
                     return_bets_only = False,
                     lower_R_bound = 1.55,
                     high_R_bound = 2.05):

        """
        Bets
        :param predictions:
        :param sportsbooks:
        :param return_bets_only:
        :return:
        """

        # TODO: Do something if predictions are None
        if predictions is None:
            predictions = self.predict()

        # Retreive the odds and merge them with the game predictions
        if 'home_odds' not in predictions.columns:
            odds = datasets.betting_df(sportsbooks = sportsbooks)
            games_df = predictions.merge(odds, on = '_id', how = 'inner')
        else:
            games_df = predictions

        # Get the R value for each game based on the abilities
        hbp = 1/games_df['home_odds']
        abp = 1/games_df['away_odds']

        # Adjust the odds to remove the bookies take
        take = hbp + abp
        games_df['hbp'] = hbp / take
        games_df['abp'] = abp / take

        # Calculate R value
        games_df['home_R'] = games_df['hprob'] / games_df['hbp']
        games_df['away_R'] = games_df['aprob'] / games_df['abp']

        # floor to two decimal places
        games_df['home_R'] = np.floor(games_df['home_R'] * 100) / 100
        games_df['away_R'] = np.floor(games_df['away_R'] * 100) / 100

        if return_bets_only:
            return games_df[(((games_df.home_R >= lower_R_bound) & (games_df.home_R <= high_R_bound)) | ((games_df.away_R >= lower_R_bound) & (games_df.away_R < high_R_bound)))]
        else:
            return games_df


    def today_games(self,
                    sportsbooks = ['Pinnacle Sports', 'bet365', 'SportsInteraction'],
                    bets_only = True,
                    keep_abilities = False):

        today = team_scraper.scrape_betting_page().reset_index(drop=True)

        # Filter for the sportsbooks
        if sportsbooks is not None:
            today = today[today.sportsbook.isin(sportsbooks)]

        # TODO: Dynamic method to include the current week vs. hardcode
        today['week'] = self.week

        predictions = self.predict(today, keep_abilities = keep_abilities)
        bets = self.games_to_bet(predictions, return_bets_only = bets_only)

        return bets

    def accuracy_by_season(self, predictions = None):

        if predictions is None:
            predictions = self.predict()

        return predictions.groupby(['season']).apply(lambda x: pd.Series({'home_percentage': pu.home_accuracy(x),
                                                                          'home_count': sum(x.hprob > x.aprob),
                                                                          'away_percentage': pu.away_accuracy(x),
                                                                          'away_count': sum(x.aprob > x.hprob),
                                                                          'total_percentage': pu.win_accuracy(x)}))
