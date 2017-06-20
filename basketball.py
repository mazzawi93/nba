import string

import numpy as np
from scipy.optimize import minimize

from db import datasets
from db import process_utils
from models import dixon_robinson as dr


class Basketball:
    def __init__(self, nba, nteams=4, ngames=4, nmargin=10, season=None):

        if season is None:
            season = [2016]

        self.opt = None

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

    def dixon_robinson(self, model=0):

        # Initial Guess for the minimization
        ab = self.initial_guess(model)

        # Minimize Constraint
        con = {'type': 'eq', 'fun': dr.attack_constraint, 'args': (self.nteams,)}

        # Minimize the likelihood function
        self.opt = minimize(dr.dixon_robinson, x0=ab, args=(self.dataset.as_matrix(), self.teams, model), constraints=con)

    def print_abilities(self):
        """
        Print the team parameters (attack, defense and home) in a neat format
        """

        if self.opt is not None:

            print('Team\tAttack\tDefence')

            i = 0
            for team in self.teams:
                print('%s\t\t%.2f\t%.2f' % (team, self.opt.x[i], self.opt.x[i+self.nteams]))
                i += 1

            print("Home Advantage:\t%.2f" % self.opt.x[self.nteams*2])








