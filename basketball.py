import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

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

        # Base model only contains the home advantage
        if model == 1:
            params = np.full((1, self.nteams + 1), 1.5)
        # The time parameters are added to the model
        elif model == 2:
            params = np.full((1, self.nteams + 5), 1.5)
        # Model is extended by adding scoreline parameters if a team is winning
        elif model == 3:
            params = np.full((1, self.nteams + 9), 1.5)
        # Extend model with larger winning margins
        elif model == 4:
            params = np.full((1, self.nteams + 17), 1.5)
        # Time Rates
        elif model == 5:
            params = np.full((1, self.nteams + 7), 1.5)
        else:
            params = np.full((1, self.nteams + 1), 1)

        return np.append(att, params)

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

        self.abilities = {}
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

    def test_model(self, model=0, season=None, month=None):
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

            test = datasets.match_point_times(season, month)
        else:
            test = datasets.create_test_set(self.nteams, self.ngames, self.nmargin)

        predict = 0
        ngames = 0

        for row in test.itertuples():
            hmean = self.abilities[row.home]['att'] * self.abilities[row.away]['def'] * self.abilities['home']
            amean = self.abilities[row.away]['att'] * self.abilities[row.home]['def']

            homea, awaya = 0, 0
            for h in range(1, 150):
                for a in range(1, 150):

                    if h > a:
                        homea += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))
                    elif h < a:
                        awaya += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))

            if hmean >= amean:
                predicted = row.home
            else:
                predicted = row.away

            if row.home_pts > row.away_pts:
                winner = row.home
            else:
                winner = row.away

            if predicted == winner:
                predict += 1
            ngames += 1

            print("%s: %.4f\t\t%s: %.4f\t\tWinner: %s\t\t%d/%d\t%.4f" % (
            row.home, homea, row.away, awaya, winner, predict, ngames, (predict / ngames)))

        print("Prediction Accuracy: %.4f" % (predict / ngames))
