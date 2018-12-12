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
        today = datetime.datetime.now()
        self.week = int(today.strftime("%U")) +  (today.year % 2010 * 52)

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

        # Get all week numbers from 2015 season
        first_week = datasets.game_results(2015)['week'].min()

        # Generate abilities for each week
        # TODO: Don't do range as it does all weeks in the offseason
        for w in range(first_week, self.week + 1):
            self.train_week(w)


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

        if kwargs.get('R_percent', True):
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
                    R_percent = True):



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


    def betting_accuracy(self, predictions, **kwargs):

        betting = self.games_to_bet(predictions, sportsbooks = kwargs.get('sportsbooks', None), R_percent = kwargs.get('R_percent', True))

        writer = pd.ExcelWriter(kwargs.get('file_name', 'betting.xlsx'))

        # Optimal Betting Strategy
        fluc_allowance = kwargs.get('fluc_allowance', 1.5)
        risk_tolerance = kwargs.get('risk_tolerance', 10)
        starting_bankroll = kwargs.get('starting_bankroll', 2000)

        low_r = kwargs.get('low_r', 1)
        high_r = kwargs.get('high_r', 1)

        r = np.arange(low_r, high_r, 0.05)

        # Create sheet for each year
        for year, games in betting.groupby('season'):

            df = pd.DataFrame()

            # R lower limit
            for lr in r:

                lr = round(lr, 2)

                # R upper limit
                for hr in np.arange(lr+0.05, high_r, 0.05):

                    hr = round(hr, 2)

                    stats = {'low_r': lr, 'high_r': hr}

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

                    for game_id, game in games.groupby('_id'):

                        # Bet on home team when it fits the R value
                        home_bet = np.logical_and(game.home_R < hr, game.home_R >= lr)

                        # Bet on away team when it fits the R value
                        away_bet = np.logical_and(game.away_R < hr, game.away_R >= lr)

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

                    df = df.append(pd.DataFrame(stats, index = [0]), ignore_index = True)

                df.to_excel(writer, str(year), index = False)

        writer.save()
