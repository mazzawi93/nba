import time
import datetime
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from db import datasets, mongo, process_utils
from models import nba_models as nba
from models import prediction_utils as pu
from scrape import scrape_utils, team_scraper, player_scraper

class nba_model:

    def __init__(self, mw, att_constraint, def_constraint, day_span = 7):

        # Team Information
        self.nteams = 30
        self.teams = process_utils.name_teams(False, 30)

        # MongoDB
        self.mongo = mongo.Mongo()

        # Model parameters
        self.mw = mw
        self.att_constraint = att_constraint
        self.def_constraint = def_constraint
        self.day_span = day_span

        self.today = datetime.datetime.now()
        self.today = pd.Timestamp(self.today.replace(hour=0, minute=0, second=0, microsecond=0))

        # Train new abilities if they don't exist in the database
        if self.mongo.count(self.mongo.DIXON_TEAM,
                            {'mw': self.mw,
                             'att_constraint': self.att_constraint,
                             'def_constraint': self.def_constraint,
                             'day_span': self.day_span}) == 0:
            print('Training Team Abilities')
            self.train_all(teams = True, players = False)
        # ELIF TRAIN MISSING DAYS
        elif self.mongo.count(self.mongo.DIXON_TEAM,
                              {
                                'mw': self.mw,
                                'att_constraint': self.att_constraint,
                                'def_constraint': self.def_constraint,
                                'day_span': self.day_span,
                                'date': self.today
                              }) == 0:

            print('Scraping Missing Games')
            for team in scrape_utils.team_names():
                team_scraper.season_game_logs(team, 2019)


            print('Training Missing Days (Including Today)')
            ab = datasets.team_abilities(mw, att_constraint, def_constraint, day_span)
            games = datasets.game_results([2017, 2018, 2019])

            missing_ab = ab.merge(games, on = 'date', how = 'right')

            # Train for the missing dates
            for date in missing_ab.loc[missing_ab.team.isnull(), 'date'].unique():
                self.train(pd.Timestamp(date))

            # Need to add today as this won't include that
            self.train(self.today)

        # Train new abilities if they don't exist in the database
        if self.mongo.count(self.mongo.PLAYERS_BETA, {'mw': 0.044, 'day_span': self.day_span}) == 0:
            print('Training Player Abilities')
            self.train_all(teams = False, players = True)
        # ELIF TRAIN MISSING DAYS
        elif self.mongo.count(self.mongo.PLAYERS_BETA, {'mw': 0.044, 'day_span': self.day_span, 'date': self.today}) == 0:

            ab = datasets.player_abilities(0.044, day_span)
            games = datasets.game_results([2017, 2018, 2019])

            # Determine which games need to be scraped
            missing_ab = ab.merge(games, on = 'date', how = 'right')
            missing_ids = missing_ab[missing_ab['mean'].isnull()]['_id'].unique()

            # Scrape the missing game logs
            print('Scraping Player Box Scpres')
            for id in missing_ids:
                player_scraper.player_box_score(id)

            # Train for the missing dates
            print('Train Missing Days')
            for date in missing_ab.loc[missing_ab.team.isnull(), 'date'].unique():
                self.train_players(pd.Timestamp(date))

            # Need to add today as this won't include that
            self.train_players(self.today)

        # Get all abilities in DF
        self.abilities = datasets.team_abilities(mw, att_constraint, def_constraint, day_span)
        self.player_abilities = datasets.player_abilities(0.044, day_span)

    def train_all(self, teams = True, players = True):
        """
        Train parameters for all weeks.

        Args:
            teams: Boolean - Train teams parameters if True
            players: Boolean - Train player parameters if True

        """

        # Train every date in dataset
        for date in datasets.game_results([2017, 2018, 2019])['date'].unique():

            # Train Team Poisson Distributions
            if teams:
                self.train(pd.Timestamp(date))

            # Train Player Beta Distributions
            if players:
                self.train_players(pd.Timestamp(date))

    def train_players(self, date = None, years_to_keep = 2):

        if date is None:
            date = self.today

        # Only keep the last two seasons
        df = datasets.player_results(date = date)
        df = df[((date - df['date']).dt.days) < (365*2)]

        self.mongo.remove(
            self.mongo.PLAYERS_BETA,
            {
                'mw': 0.044,
                'day_span' : 7,
                'date': date
            }
        )

        print(date)

        con = [{'type': 'ineq', 'fun': lambda x: x[0]}, {'type': 'ineq', 'fun': lambda x: x[1]}]

        df.loc[df.pts == 0, 'pts'] = 0.001
        for name, games in df.groupby('player'):

            player = {'date': date, 'mw': 0.044, 'day_span': 7}

            a0 = np.array([games.team_pts.mean(), (games.team_pts - games.pts).mean()])

            opt = minimize(nba.player_beta, x0=a0, args=(games, date, self.day_span, self.mw), constraints = con)

            player['player'] = {'name': str(name), 'a': opt.x[0], 'b': opt.x[1], 'team': games[games.date == games.date.max()]['team'].to_string(index = False)}

            self.mongo.insert(self.mongo.PLAYERS_BETA, player)

    def train(self, date = None, years_to_keep = 2):

        if date is None:
            date = self.today

        # Only keep the last two seasons
        df = datasets.game_results(teams = self.teams, date = date)
        df = df[((date - df['date']).dt.days) < (365*years_to_keep)]

        # Remove abilities from DB
        self.mongo.remove(self.mongo.DIXON_TEAM,
                          {
                            'mw': self.mw,
                            'att_constraint': self.att_constraint,
                            'def_constraint': self.def_constraint,
                            'day_period': self.day_span,
                            'date': date
                          })

        # Initial Guess
        a0 = pu.initial_guess(0, self.nteams)

        if self.att_constraint == 'rolling':
            weight = np.exp(-self.mw * np.ceil(((date - df['date']).dt.days) / self.day_span))
            att_constraint = np.average(df['away_pts'], weights = weight)
        elif self.att_constraint == 'rolling_low':
            weight = np.exp(-self.mw * np.ceil(((date - df['date']).dt.days) / self.day_span))
            att_constraint = np.floor((np.average(df['away_pts'], weights = weight) + 100)/2)

        else:
            att_constraint = self.att_constraint

        con = []

        print(date, att_constraint)

        if self.att_constraint is not None:
            con.append({'type': 'eq', 'fun': pu.attack_constraint, 'args': (round(att_constraint), self.nteams,)})

        if self.def_constraint is not None:
            con.append({'type': 'eq', 'fun': pu.defense_constraint, 'args': (round(self.def_constraint), self.nteams,)})

        # Get team parameters for the current week
        opt = minimize(nba.dixon_coles, x0=a0, args=(df, self.nteams, date, self.day_span, self.mw), constraints = con, method='SLSQP')

        abilities = pu.convert_abilities(opt.x, self.teams)

        # Store weekly abilities
        abilities['day_span'] = self.day_span
        abilities['mw'] = self.mw

        # Constraints
        abilities['att_constraint'] = self.att_constraint
        abilities['def_constraint'] = self.def_constraint
        abilities['date'] = date

        self.mongo.insert(self.mongo.DIXON_TEAM, abilities)


    def predict(self, dataset = None, seasons = None, keep_abilities = False, players = False, player_penalty = 0.22, top_players = 1):
        """
        Game predictions based on the team.
        """

        # Get the dataset if required
        if dataset is None:
            games = datasets.game_results(season = seasons)
        else:
            games = dataset

        # Merge the team abilities to the results
        games = games.merge(self.abilities, left_on = ['date', 'home_team'], right_on = ['date', 'team']) \
        .merge(self.abilities, left_on = ['date', 'away_team'], right_on = ['date', 'team'])

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

        if players:

            player_abilities = datasets.player_abilities(decay=0.044, day_span = 7)

            player_abilities['rank'] = player_abilities.groupby(['team', 'date'])['mean'].rank(ascending = False)

            player_abilities = player_abilities[player_abilities['rank'] <= top_players]

            # Get the players who played in a game, not just best player
            pr = datasets.player_results().astype(str)

            # Iterate through each game and apply penalty if best player is missing
            for game in games.itertuples():

                players = pr[pr._id==game._1]['player'].values

                # Home Penalty
                bp = player_abilities.loc[(player_abilities.team == game.home_team) & (player_abilities.date == game.date)]
                penalty = 1 - (bp['mean'] * ~bp['name'].isin(players) * player_penalty)
                games.loc[games._id == game._1, 'home_mean'] = penalty.cumprod().min() * games.loc[games._id == game._1, 'home_mean']

                # Away Penalty
                bp = player_abilities.loc[(player_abilities.team == game.away_team) & (player_abilities.date == game.date)]
                penalty = 1 - (bp['mean'] * ~bp['name'].isin(players) * player_penalty)
                games.loc[games._id == game._1, 'away_mean'] = penalty.cumprod().min() * games.loc[games._id == game._1, 'away_mean']

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

        low_R = kwargs.get('low_R', 1.55)
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
            return games_df[(((games_df.home_R >= low_R) & (games_df.home_R <= high_R)) | ((games_df.away_R >= low_R) & (games_df.away_R < high_R)))]
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

        today['date'] = self.today

        predictions = self.predict(today, keep_abilities = keep_abilities)
        bets = self.games_to_bet(predictions, return_bets_only = bets_only, R_percent = R_percent)

        bets = bets.sort_values(['home_team', 'sportsbook'])

        bets['home_odds_needed'] = round(1.5*bets['model_h_odds'], 2)
        bets['away_odds_needed'] = round(1.5*bets['model_a_odds'], 2)

        bets = bets[['date', 'sportsbook', 'home_team', 'hprob', 'model_h_odds', 'home_R', 'home_odds', 'home_odds_needed', 'away_team', 'aprob', 'model_a_odds', 'away_R', 'away_odds', 'away_odds_needed']]

        if file_name is not None:
            bets.to_csv(file_name, index=False)

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
        """
        Args:


        """

        betting = self.games_to_bet(predictions,
                                    sportsbooks = kwargs.get('sportsbooks', None),
                                    R_percent = kwargs.get('R_percent', False))

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

            df = pd.DataFrame()

            # Simulate the bets for each range
            for lr in r:
                for hr in np.arange(lr+0.05, high_r+0.05, 0.05):

                    season_df = pd.DataFrame(pu.bet_season(games, lr, hr, **kwargs))
                    df = df.append(season_df, ignore_index = True)

                # Write the season to excel
                df.to_excel(writer, '-'.join(str(e) for e in n), index = False)

        # Save the excel file
        writer.save()
