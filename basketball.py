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

    def __init__(self, mw, att_constraint, def_constraint):

        # Team Information
        self.nteams = 30
        self.teams = process_utils.name_teams(False, 30)

        # MongoDB
        self.mongo = mongo.Mongo()

        # Model parameters
        self.mw = mw
        self.att_constraint = att_constraint
        self.def_constraint = def_constraint

        # Set to the current week
        self.today = datetime.datetime.now()
        self.week = int(self.today.strftime("%U")) +  (self.today.year % 2010 * 52)

        # Train new abilities if they don't exist in the database
        if self.mongo.count(self.mongo.DIXON_TEAM, {'mw': self.mw, 'att_constraint': self.att_constraint, 'def_constraint': self.def_constraint}) == 0:
            print('Training All Weeks')
            self.train_all()
        elif self.mongo.count(self.mongo.DIXON_TEAM, {'mw': self.mw, 'att_constraint': self.att_constraint, 'def_constraint': self.def_constraint, 'week': self.week}) == 0:
            print('Training Current Week')
            # TODO: Scrape game logs of last week
            self.train_week()

        # Get all abilities in DF
        self.abilities = datasets.team_abilities(mw, att_constraint, def_constraint)

    def train_all(self):

        weeks = datasets.game_results([2015, 2016, 2017, 2018, 2019])['week'].unique()

        # Generate abilities for each week
        # TODO: Don't do range as it does all weeks in the offseason
        for w in weeks:
            self.train_week(int(w))


    def train_week(self, week = None):

        # If week is None, then use the current week
        if week is None:
            week = self.week

        # Get all games in DB before given week
        df = datasets.game_results(teams = self.teams, week = week)

        # Remove abilities from DB
        self.mongo.remove(self.mongo.DIXON_TEAM, {'mw': self.mw, 'att_constraint': self.att_constraint, 'def_constraint': self.def_constraint, 'week': week})

        # Initial Guess
        a0 = pu.initial_guess(0, self.nteams)

        if self.att_constraint == 'rolling':
            weight = np.exp(-self.mw * (week - df['week']))
            att_constraint = np.average(np.append(df['home_pts'], df['away_pts']), weights = np.append(weight, weight))
        else:
            att_constraint = self.att_constraint

        con = []

        print(week, att_constraint)

        np.exp(-0.044 * np.arange(1, 100))

        if self.att_constraint is not None:
            con.append({'type': 'eq', 'fun': pu.attack_constraint, 'args': (round(att_constraint), self.nteams,)})

        if self.def_constraint is not None:
            con.append({'type': 'eq', 'fun': pu.defense_constraint, 'args': (round(self.def_constraint), self.nteams,)})

        # Get team parameters for the current week
        opt = minimize(nba.dixon_coles, x0=a0, args=(df, self.nteams, week, self.mw), constraints = con, method='SLSQP')

        abilities = pu.convert_abilities(opt.x, self.teams)

        # Store weekly abilities
        abilities['week'] = int(week)
        abilities['mw'] = self.mw

        # Constraints
        abilities['att_constraint'] = self.att_constraint
        abilities['def_constraint'] = self.def_constraint

        self.mongo.insert(self.mongo.DIXON_TEAM, abilities)


    def predict(self, dataset = None, seasons = None, keep_abilities = False, sample = False):
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

        if sample:

            games[['hprob', 'aprob']] = games.apply(pu.determine_probabilities_sample, axis = 1)

            scale = 1 / (games['hprob'] + games['aprob'])

            games['hprob'] = games['hprob'] * scale
            games['aprob'] = games['aprob'] * scale

        else:

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

            # Add probabilities to DF
            games['hprob'] = hprob
            games['aprob'] = aprob

        # Drop columns we don't want
        if not keep_abilities:
            games = games.drop(['home_attack', 'home_defence', 'home_adv', 'away_attack', 'away_defence', 'home_mean', 'away_mean'], axis = 1)

        # Try to sort by date, but if date doesn't exist it doesn't matter
        try:
            games = games.sort_values('date').reset_index(drop = True)
        except KeyError:
            games = games.reset_index(drop = True)

        return games


    def games_to_bet(self, predictions, **kwargs):
        """
        sportsbook
        R_percent
        return_bets_only
        home_low_R
        away_low_R
        high_R
        """

        home_low_R = kwargs.get('home_low_R', 1.55)
        away_low_R = kwargs.get('away_low_R', 1)
        high_R = kwargs.get('high_R', 2.05)

        # Retreive the odds and merge them with the game predictions
        if 'home_odds' not in predictions.columns:
            odds = datasets.betting_df(sportsbooks = kwargs.get('sportsbooks', None))
            games_df = predictions.merge(odds, on = '_id', how = 'inner')
        else:
            games_df = predictions

        if kwargs.get('R_percent', False):
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
        else:

            games_df['model_h_odds'] = 1/games_df['hprob']
            games_df['model_a_odds'] = 1/games_df['aprob']

            games_df['home_R'] = games_df['home_odds']/games_df['model_h_odds']
            games_df['away_R'] = games_df['away_odds']/games_df['model_a_odds']

        # floor to two decimal places
        games_df['home_R'] = np.floor(games_df['home_R'] * 100) / 100
        games_df['away_R'] = np.floor(games_df['away_R'] * 100) / 100

        if kwargs.get('return_bets_only', False):
            return games_df[(((games_df.home_R >= home_low_R) & (games_df.home_R <= high_R)) | ((games_df.away_R >= away_low_R) & (games_df.away_R < high_R)))]
        else:
            return games_df


    def today_games(self,
                    sportsbooks = ['Pinnacle Sports', 'bet365', 'SportsInteraction'],
                    bets_only = True,
                    keep_abilities = False,
                    R_percent = False):



        url = 'https://classic.sportsbookreview.com/betting-odds/nba-basketball/money-line/'

        today = team_scraper.scrape_betting_page(url).reset_index(drop=True)

        # Filter for the sportsbooks
        if sportsbooks is not None:
            today = today[today.sportsbook.isin(sportsbooks)]

        today['week'] = self.week

        predictions = self.predict(today, keep_abilities = keep_abilities)
        bets = self.games_to_bet(predictions, return_bets_only = bets_only, R_percent = R_percent)

        return bets

    def accuracy_by_season(self, predictions = None):

        if predictions is None:
            predictions = self.predict()

        return predictions.groupby(['season']).apply(lambda x: pd.Series({'home_percentage': pu.home_accuracy(x),
                                                                          'home_count': sum(x.hprob > x.aprob),
                                                                          'away_percentage': pu.away_accuracy(x),
                                                                          'away_count': sum(x.aprob > x.hprob),
                                                                          'total_percentage': pu.win_accuracy(x),
                                                                          's': np.dot(np.log(x.hprob), x.home_pts > x.away_pts) + np.dot(np.log(x.aprob), x.away_pts > x.home_pts)}))


    def betting_profit(self, predictions, df = None, **kwargs):

        betting = self.games_to_bet(predictions, sportsbooks = kwargs.get('sportsbooks', None), R_percent = kwargs.get('R_percent', True))

        # Years to bet
        years = kwargs.get('years', [[2019], [2018, 2019], [2017, 2018, 2019]])

        # Create a new DF if not appending to an old one
        if df is None:
            df = pd.DataFrame()

        # Iterate trough each year and append to DF
        for n in years:

            # Games in the defined season
            games = betting[betting.season.isin(n)]

            # Simulate season
            df = pu.bet_season(games, kwargs.get('low_r', 1.55), kwargs.get('high_r', 2.7), **kwargs)

        return df


    def betting_ranges(self, predictions, **kwargs):

        # Get R values for predictions
        betting = self.games_to_bet(predictions,
                                    sportsbooks = kwargs.get('sportsbooks', ['SportsInteraction', 'Pinnacle Sports', 'bet365']),
                                    R_percent = kwargs.get('R_percent', False))

        # Excel Writer
        writer = pd.ExcelWriter(kwargs.get('file_name', 'betting.xlsx'))

        # R ranges
        low_r = kwargs.get('low_r', 1)
        high_r = kwargs.get('high_r', 3)

        r = np.arange(low_r, 2.15, 0.05)

        # Seasons to bet
        years = kwargs.get('years', [[2019], [2018, 2019], [2017, 2018, 2019]])

        # Create sheet for each year
        for n in years:

            games = betting[betting.season.isin(n)]

            # Simulate the bets for each range
            for lr in r:
                for hr in np.arange(lr+0.05, high_r+0.05, 0.05):

                    season_df = pd.DataFrame(games, lr, hr, **kwargs)
                    df = df.append(season_df, index = False)

                # Write the season to excel
                df.to_excel(writer, '-'.join(str(e) for e in n), index = False)

        # Save the excel file
        writer.save()
