import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson
from pymongo import MongoClient
from bson.objectid import ObjectId
from db import datasets
from db import process_utils
from models import dixon_robinson as dr


class Basketball:
    def __init__(self, nba, nteams=4, ngames=4, nmargin=10, season=None, month=None):

        if season is None:
            season = 2016

        self.opt = None
        self.nba = nba
        self.abilities = None

        if nba is True:

            self.dataset = datasets.match_point_times(season=season, month=month)
            self.teams = process_utils.name_teams(True)
            self.nteams = 30
            self.season = season
            self.month = month

        else:

            if nteams < 2:
                raise ValueError('There must be at least two teams.')

            if ngames % 2 != 0:
                raise ValueError('The number of games must be even so there is equal home and away.')

            self.dataset = datasets.create_test_set(nteams, ngames, nmargin)
            self.teams = process_utils.name_teams(False, nteams)
            self.nteams = nteams
            self.ngames = ngames
            self.nmargin = nmargin

    def initial_guess(self, model=1):
        """
        Create an initial guess for the minimization function
        :param model: The model implemented (1 = Base model (Att, Def, Home), 2 = Time Parameters, 3 = winning/losing)
        :return: Numpy array of team abilities (Attack, Defense) and Home Advantage and other factors
        """

        # Attack and Defence parameters
        att = np.full((1, self.nteams), 100)
        defense = np.full((1, self.nteams), 1)
        teams = np.append(att, defense)

        # Base model only contains the home advantage
        if model == 1:
            params = np.full((1, 1), 1.5)
        # The time parameters are added to the model
        elif model == 2:
            params = np.full((1, 5), 1.5)
        # Model is extended by adding scoreline parameters if a team is winning
        elif model == 3:
            params = np.full((1, 9), 1.5)
        # Extend model with larger winning margins
        elif model == 4:
            params = np.full((1, 17), 1.5)
        # Time Rates
        elif model == 5:
            params = np.full((1, 7), 1.5)
        else:
            params = np.full((1, 1), 1.5)

        return np.append(teams, params)

    def dixon_coles(self):
        """
        Apply the dixon coles model to an NBA season to find the attack and defense parameters for each team
        as well as the home court advantage
        """

        # Initial Guess for the minimization
        ab = self.initial_guess()

        # Game Data without time
        nba = self.dataset
        nba = nba.drop('time', axis=1)

        # Minimize Constraint
        con = {'type': 'eq', 'fun': dr.attack_constraint, 'args': (self.nteams,)}

        # Minimize the likelihood function
        self.opt = minimize(dr.dixon_coles, x0=ab, args=(nba, self.teams), constraints=con)

        self.ab(self.opt.x)

    def dixon_robinson(self, model=1):
        """
        Dixon-Robinson implementation
        :param model: The model number (0 = no time or scoreline parameters)
        """

        # Initial Guess for the minimization
        ab = self.initial_guess(model)

        # Minimize Constraint
        con = {'type': 'eq', 'fun': dr.attack_constraint, 'args': (self.nteams,)}

        # Minimize the likelihood function
        self.opt = minimize(dr.dixon_robinson, x0=ab, args=(self.dataset, self.teams, model),
                            constraints=con)

        self.ab(self.opt.x, model)

    def ab(self, opt, model=1):
        """
        Convert the abilities numpy array into a more usable dict
        :param opt: Abilities from optimization
        :param model: Model number determines which parameters are included
        """

        self.abilities = {
            'model': model
        }
        i = 0

        # Attack and defense
        for team in self.teams:
            self.abilities[team] = {
                'att': opt[i],
                'def': opt[i + self.nteams]
            }
            i += 1

        # Home Advantage
        self.abilities['home'] = opt[self.nteams * 2]

        # Time parameters
        if model >= 2:
            self.abilities['time'] = {
                'q1': opt[self.nteams * 2 + 1],
                'q2': opt[self.nteams * 2 + 2],
                'q3': opt[self.nteams * 2 + 3],
                'q4': opt[self.nteams * 2 + 4]
            }

        if model == 3:
            self.abilities['lambda'] = {
                '+1': opt[self.nteams * 2 + 5],
                '-1': opt[self.nteams * 2 + 6],
            }
            self.abilities['mu'] = {
                '+1': opt[self.nteams * 2 + 7],
                '-1': opt[self.nteams * 2 + 8]
            }
        elif model == 4:
            self.abilities['lambda'] = {
                '+1': opt[self.nteams * 2 + 5],
                '-1': opt[self.nteams * 2 + 6],
                '+2': opt[self.nteams * 2 + 11],
                '-2': opt[self.nteams * 2 + 12],
                '+3': opt[self.nteams * 2 + 9],
                '-3': opt[self.nteams * 2 + 10],
            }
            self.abilities['mu'] = {
                '+1': opt[self.nteams * 2 + 7],
                '-1': opt[self.nteams * 2 + 8],
                '+2': opt[self.nteams * 2 + 15],
                '-2': opt[self.nteams * 2 + 16],
                '+3': opt[self.nteams * 2 + 13],
                '-3': opt[self.nteams * 2 + 14]
            }

        if model == 5:
            self.abilities['time']['home'] = opt[self.nteams * 2 + 5]
            self.abilities['time']['away'] = opt[self.nteams * 2 + 6]

    def test_model(self, season=None, month=None, display=False):
        """
        Test the optimized model against a testing set
        :param season: NBA Season
        :return: Accuracy of the model
        """

        # If it is nba data we are working with get current season, else create a testing set with the same
        # parameters as the training set
        if self.nba is True:
            if season is None:
                season = [2017]

            test = datasets.match_point_times(season, month, bet=True)
        else:
            test = datasets.create_test_set(self.nteams, self.ngames, self.nmargin)

        bankroll = 0

        nbets, nwins = 0, 0
        npredict, ntotal = 0, 0

        for row in test.itertuples():

            # Bet on respective teams
            hbet = False
            abet = False

            # Poisson Means
            hmean = self.abilities[row.home]['att'] * self.abilities[row.away]['def'] * self.abilities['home']
            amean = self.abilities[row.away]['att'] * self.abilities[row.home]['def']

            # Calculate probabilities
            hprob, aprob = 0, 0
            for h in range(60, 140):
                for a in range(60, 140):

                    if h > a:
                        hprob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))
                    elif h < a:
                        aprob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))

            # Implied probability from betting lines (ie. 2.00 line means 50% chance they win)
            hbp = 1/row.home_bet
            abp = 1/row.away_bet

            # Determine if we should bet on the home and away team
            if hprob >= hbp:
                hbet = True
            if aprob >= abp:
                abet = True

            # Determine prediction
            if hprob >= aprob:
                predict = row.home
            else:
                predict = row.away

            if row.home_pts > row.away_pts:
                winner = row.home

                if hbet:
                    bankroll += row.home_bet - 1
                    nbets += 1
                    nwins += 1

                if abet:
                    bankroll -= 1
                    nbets += 1

            else:
                winner = row.away

                if hbet:
                    bankroll -= 1
                    nbets += 1

                if abet:
                    bankroll += row.away_bet - 1
                    nbets += 1
                    nwins += 1

            if predict == winner:
                npredict += 1

            ntotal += 1

            if display:
                print("%s (%.2f): %.4f\t\t%s (%.2f): %.4f" % (row.home, row.home_bet, hprob, row.away, row.away_bet, aprob))
                print("Home Bet: %s\t\t\tAway Bet: %s\t\t" % (hbet, abet))
                print("Predicted: %s\t\t\tWinner: %s\t\t\tPercentage: %.4f" % (predict, winner, (npredict/ntotal)))
                print("Number of bets: %d\t\tNum of wins: %d\t\tPercentage: %.4f" % (nbets, nwins, (nwins/nbets)))
                print("Bankroll: %.2f"  % bankroll)
                print()

        print("Predicted: %d/%d\t\tPercentage: %.4f" % (npredict, ntotal, (npredict / ntotal)))
        print("Number of bets: %d\t\tNum of wins: %d\t\tPercentage: %.4f" % (nbets, nwins, (nwins / nbets)))
        print("Bankroll: %.2f" % bankroll)


    def store_abilities(self):
        """
        Store team abilities in MongoDB
        """

        if self.nba is True:
            client = MongoClient()
            db = client.basketball
            collection = db.abilities

            abilities = self.abilities
            abilities['season'] = self.season
            collection.insert(abilities)

            client.close()

    def load_abilities(self, model=1, id = None):
        """
        Load team abilities from mongoDB
        :param model: The Dixon Robinson model
        """

        if self.nba is True:
            client = MongoClient()
            db = client.basketball
            collection = db.abilities

            if id is not None:
                ab = collection.find_one({'_id': ObjectId(id)})
            else:
                ab = collection.find_one({'year': self.season, 'model': model})

            if ab is None:
                print('No parameters found for this model and season.')
            else:
                self.abilities = ab
                client.close()