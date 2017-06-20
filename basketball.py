import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from db import datasets
from db import process_utils
from models import dixon_robinson as dr


class Basketball:
    def __init__(self, nba, nteams=4, ngames=4, nmargin=10, season=None):

        if season is None:
            season = [2016]

        self.opt = None
        self.nba = nba
        self.abilities = None

        if nba is True:

            self.dataset = datasets.match_point_times(season)
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

    def initial_guess(self, model=0):
        """
        Create an initial guess for the minimization function
        :param model:
        :return: Numpy array of team abilities (Attack, Defense) and Home Advantage
        """

        att = np.full((1, self.nteams), 100)

        if model == 0:
            dh = np.full((1, self.nteams + 1), 1)
        # The time parameters are added to the model
        elif model == 1:
            dh = np.full((1, self.nteams + 5), 1)
        else:
            dh = np.full((1, self.nteams + 1), 1)

        return np.append(att, dh)

    def dixon_coles(self):
        """
        Apply the dixon coles model to an NBA season to find the attack and defense parameters for each team
        as well as the home court advantage
        :param season: NBA Season
        :return:
        """

        # Initial Guess for the minimization
        ab = self.initial_guess()

        # Game Data without time
        nba = self.dataset
        nba = nba.drop('time', axis=1)
        nba = nba.as_matrix()

        # Minimize Constraint
        con = {'type': 'eq', 'fun': dr.attack_constraint, 'args': (self.nteams,)}

        # Minimize the likelihood function
        self.opt = minimize(dr.dixon_coles, x0=ab, args=(nba, self.teams), constraints=con)

        self.ab(self.opt.x)

    def dixon_robinson(self, model=0):
        """
        Dixon-Robinson implementation
        :param model: The model number (0 = no time or scoreline parameters)
        """

        # Initial Guess for the minimization
        ab = self.initial_guess(model)

        # Minimize Constraint
        con = {'type': 'eq', 'fun': dr.attack_constraint, 'args': (self.nteams,)}

        # Minimize the likelihood function
        self.opt = minimize(dr.dixon_robinson, x0=ab, args=(self.dataset.as_matrix(), self.teams, model),
                            constraints=con)

        self.ab(self.opt.x)

    def ab(self, opt):

        self.abilities = {}

        i = 0
        for team in self.teams:
            self.abilities[team] = {
                'att': opt[i],
                'def': opt[i + self.nteams]
            }
            i += 1

        self.abilities['home'] = opt[self.nteams * 2]

    def test_model(self, season = None):

        if self.nba is True:
            if season is None:
                season = [2017]

            test = datasets.match_point_times(season)
        else:
            test = datasets.create_test_set(self.nteams, self.ngames, self.nmargin)

        predict = 0
        ngames = 0
        for row in test.itertuples():
            hmean = self.abilities[row.home]['att'] * self.abilities[row.away]['def'] * self.abilities['home']
            amean = self.abilities[row.away]['att'] * self.abilities[row.home]['def']

            hpts = poisson.rvs(mu=hmean, size=1000)
            apts = poisson.rvs(mu=amean, size=1000)

            hwin, awin = 0, 0

            for i in range(1000):
                if hpts[i] >= apts[i]:
                    hwin += 1
                else:
                    awin += 1

            if hwin >= awin:
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

            print("%s: %.4f\t\t%s: %.4f\t\tWinner: %s" % (row.home, hwin/1000, row.away, awin/1000, winner))

        print("Prediction Accuracy: %.4f" % (predict/ngames))