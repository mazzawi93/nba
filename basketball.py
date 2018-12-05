import time

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from db import datasets, mongo, process_utils
from models import nba_models as nba
from models import prediction_utils as pu


class nba_model:

    def __init__(self, mw=0.044, att_constraint = 100, def_constraint = 1):
        """ Train the model """

        self.nteams = 30
        self.teams = process_utils.name_teams(False, 30)
        self.abilities = None

        # Value error for attack mean
        if(att_constraint != 'rolling' and not isinstance(att_constraint, int)):
            raise ValueError('Attack Constraint must be integer or "rolling"')

        # Raise error for defence constraint
        if (not isinstance(def_constraint, int) and def_constraint is not None):
            raise ValueError('Defence Constraint must be integer')


        # MongoDB
        self.mongo = mongo.Mongo()

        self.mw = mw
        self.predictions = None

        self.att_constraint = att_constraint
        self.def_constraint = def_constraint


        # Train new abilities if they don't exist in the database
        try:
            self.abilities = datasets.team_abilities(mw, att_constraint, def_constraint)
        except AttributeError:
            self.train()

    def train(self, store = True):
        """
        Compute team weekly attack, defence and home advantage parameters
        """

        # Datasets
        start_df = datasets.game_results([2013, 2014, 2015], self.teams)
        rest_df = datasets.game_results([2016, 2017, 2018, 2019], self.teams)

        # Initial Guess
        a0 = pu.initial_guess(0, self.nteams)

        abilities = []

        # Recalculate the Dixon Coles parameters every week after adding the previous week to the dataset
        for week, stats in rest_df.groupby('week'):


            if self.att_constraint == 'rolling':
                weight = np.exp(-self.mw * (week - start_df['week']))
                att_constraint = np.average(np.append(start_df['home_pts'], start_df['away_pts']), weights = np.append(weight, weight))
            else:
                att_constraint = self.att_constraint

            print(week, round(att_constraint))

            con = [{'type': 'eq', 'fun': pu.attack_constraint, 'args': (round(att_constraint), self.nteams,)}]

            if self.def_constraint is not None:
                con.append({'type': 'eq', 'fun': pu.defense_constraint, 'args': (round(self.def_constraint), self.nteams,)})

            # Get team parameters for the current week
            opt = minimize(nba.dixon_coles, x0=a0, args=(start_df, self.nteams, week, self.mw), constraints=con, method='SLSQP')

            abilities = pu.convert_abilities(opt.x, 0, self.teams)

            # Store weekly abilities
            abilities['week'] = int(week)
            abilities['mw'] = self.mw

            # Constraints
            abilities['att_constraint'] = att_constraint
            abilities['def_constraint'] = self.def_constraint

            self.mongo.insert('dixon_team', abilities)

            # Append this week to the database
            start_df = start_df.append(stats, ignore_index=True)




    def store_abilities(self):
        """ Replace the abilities in the database with the ones generated """
        print('store abilities')


    def predict(self, seasons):
        """
        Game predictions for the 2015 to 2017 NBA seasons using the weekly abilities
        """

        games = datasets.game_results(season=seasons)

        games = games.merge(self.abilities, left_on = ['week', 'home_team'], right_on = ['week', 'team']).merge(self.abilities, left_on = ['week', 'away_team'], right_on = ['week', 'team'])
        games = games.rename(columns = {'attack_x': 'home_attack', 'attack_y': 'away_attack', 'defence_x': 'home_defence', 'defence_y': 'away_defence', 'home_adv_x': 'home_adv'}).drop(['team_x', 'team_y', 'home_adv_y'], axis = 1)

        games['home_mean'] = games['home_attack'] * games['away_defence'] * games['home_adv']
        games['away_mean'] = games['away_attack'] * games['home_defence']

        # Win probabilities
        hprob = np.zeros(len(games))
        aprob = np.zeros(len(games))

        # Iterate through each game to determine the winner and prediction
        for row in games.itertuples():
            hprob[row.Index], aprob[row.Index] = pu.determine_probabilities(row.home_mean, row.away_mean)

        # Scale odds so they add to 1
        scale = 1 / (hprob + aprob)
        hprob = hprob * scale
        aprob = aprob * scale

        games = games[['_id', 'season', 'date', 'home_team', 'home_pts', 'away_pts', 'away_team']]
        games['hprob'] = hprob
        games['aprob'] = aprob

        return games.sort_values('date')


    def betting_r_one_per_sportsbook(self,
                                     any = True,
                                     sportsbooks = ['SportsInteraction', 'Pinnacle Sports', 'bet365'],
                                     to_file = False,
                                     file_name = 'betting.xlsx',
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
            home_games_bet = []
            away_games_bet = []
            profit = []
            roi = []
            rob = []

            for value in r:

                value = round(value, 2)
                bankroll = starting_bankroll
                bet_total = 0
                home_count = 0
                away_count = 0

                for game_id, game in games.groupby('_id'):

                    home_bet = game.hprob / game.hbp
                    home_bet = np.logical_and(home_bet < below_r, home_bet >= value)

                    away_bet = game.aprob / game.abp
                    away_bet = np.logical_and(away_bet < below_r, away_bet >= value)

                    if any:
                        hbet = home_bet.any()
                        abet = away_bet.any()
                    else:
                        hbet = home_bet.all()
                        abet = away_bet.all()

                    if hbet:

                        home_amount = 1/(game.home_odds.max() * fluc_allowance * risk_tolerance) * bankroll
                        bet_total += home_amount
                        home_count += 1
                        bankroll = bankroll - home_amount

                    if abet:

                        away_amount = 1/(game.away_odds.max() * fluc_allowance * risk_tolerance) * bankroll
                        bet_total += away_amount
                        bankroll = bankroll - away_amount
                        away_count += 1

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
                    roi.append((bankroll - starting_bankroll)/starting_bankroll * 100)

                if(bet_total == 0):
                    rob.append(0)
                else:
                    rob.append((bankroll-bet_total)/bet_total * 100)

                home_games_bet.append(home_count)
                away_games_bet.append(away_count)

            b = pd.DataFrame({'r': r, 'rob':rob, 'roi': roi, 'profit': profit, 'dollars_bet': dollars_bet, 'home_bet': home_games_bet, 'away_bet': away_games_bet})
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
                                              risk_tolerance = 10,
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

                bet_amount = []
                home_games = []
                away_games = []
                profit = []
                roi = []
                rob = []

                for value in r:

                    value = round(value, 2)
                    bankroll = starting_bankroll
                    bet_total = 0
                    hg = 0
                    ag = 0

                    for game, row in games2.iterrows():

                        home_bet = row.hprob / row.hbp
                        home_bet = home_bet < below_r and home_bet >= value

                        away_bet = row.aprob / row.abp
                        away_bet = away_bet < below_r and away_bet >= value

                        if home_bet:
                            home_amount = 1/(row.home_odds * fluc_allowance * risk_tolerance)*bankroll
                            bet_total += home_amount
                            hg += 1
                            bankroll = bankroll - home_amount

                        if away_bet:
                            away_amount = 1/(row.away_odds * fluc_allowance * risk_tolerance)*bankroll
                            bet_total += away_amount
                            bankroll = bankroll - away_amount
                            ag += 1

                        if home_bet:
                            if(row.home_pts > row.away_pts):
                                bankroll = bankroll + (home_amount * row.home_odds)

                        if away_bet:
                            if(row.away_pts > row.home_pts):
                                bankroll = bankroll + (away_amount * row.away_odds)


                    bet_amount.append(bet_total)
                    home_games.append(hg)
                    away_games.append(ag)

                    profit.append(bankroll - starting_bankroll)

                    if bet_total == 0:
                        roi.append(0)
                    else:
                        roi.append((bankroll - starting_bankroll)/starting_bankroll * 100)

                    if bet_total == 0:
                        rob.append(0)
                    else:
                        rob.append((bankroll - starting_bankroll)/bet_total * 100)

                b = pd.DataFrame({'r': r, 'rob':rob, 'roi': roi, 'profit': profit, 'bet_amount': bet_amount, 'home_games_bet': home_games, 'away_games_bet' : away_games})
                pd_list.append(b)
                b.to_excel(writer, str(year), index = False)
            if to_file:
                writer.save()

        return pd_list
