import time
from datetime import datetime

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from db import datasets, mongo_utils
from db import process_utils
from models import dixon_robinson as dr


def determine_probabilities(hmean, amean):
    hprob, aprob = 0, 0
    for h in range(60, 140):
        for a in range(60, 140):

            if h > a:
                hprob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))
            elif h < a:
                aprob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))

    return hprob, aprob


class Basketball:
    """
    Basketball class used to manipulate team abilities and simulate upcoming seasons
    """

    def __init__(self, test, season=None, month=None, nteams=4, ngames=4, nmargin=10):
        """
        Initialize Basketball class by setting class variables

        :param test: Fabricated Set
        :param season: NBA Season(s)
        :param month: Calendar Month(s)
        :param nteams: Number of teams for test set
        :param ngames: Number of games played between teams for test set
        :param nmargin: Winning Margin in test set
        """

        if test:
            self.nteams = nteams
            self.ngames = ngames
            self.nmargin = nmargin

        else:

            self.nteams = 30
            self.season = season
            self.month = month

        self.teams = process_utils.name_teams(test, nteams)

        self.con = [{'type': 'eq', 'fun': dr.attack_constraint, 'args': (100, self.nteams,)},
                    {'type': 'eq', 'fun': dr.defense_constraint, 'args': (1, self.nteams,)}]

        self.abilities = None

    def test_model(self, fake, season=None, month=None, display=False):
        """
        Test the optimized model against a testing set and apply a betting strategy
        :param fake:
        :param season: NBA Season(s)
        :param month: Calendar month(s)
        :param display: Print the results as they happen
        :return: Accuracy of the model
        """

        # If it is nba data we are working with get current season, else create a testing set with the same
        # parameters as the training set
        if season is None:
            season = 2017

        # Dixon model has different dataset
        if fake:
            test = datasets.create_test_set(self.nteams, self.ngames, self.nmargin)
        else:
            # Dixon Coles
            if self.abilities['model'] == 0:
                test = datasets.dc_dataframe(season=season, month=month, bet=True)
            # Dixon Robinson
            else:
                test = datasets.dr_dataframe(season=season, month=month, bet=True)

        # Betting bankroll
        bankroll = 0

        # Predictions and bet wins
        nbets, nwins = 0, 0
        npredict, ntotal = 0, 0

        for row in test.itertuples():

            # Bet on respective teams
            hbet = False
            abet = False

            # Poisson Means
            hmean = self.abilities[row.home]['att'] * self.abilities[row.away]['def'] * self.abilities['home']
            amean = self.abilities[row.home]['def'] * self.abilities[row.away]['att']

            # Calculate probabilities
            hprob, aprob = determine_probabilities(hmean, amean)

            # Implied probability from betting lines (ie. 2.00 line means 50% chance they win)
            hbp = 1 / row.hbet
            abp = 1 / row.abet

            # Determine if we should bet on the home and away team
            if float(hprob) >= hbp:
                hbet = True
            if float(aprob) >= abp:
                abet = True

            # Determine prediction
            if hprob >= aprob:
                predict = row.home
            else:
                predict = row.away

            # Determine accuracy and betting result
            if row.hpts > row.apts:
                winner = row.home

                if hbet:
                    bankroll += row.hbet - 1
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
                    bankroll += row.abet - 1
                    nbets += 1
                    nwins += 1

            if predict == winner:
                npredict += 1

            ntotal += 1

            # Game by game summary
            if display:
                print("%s (%.2f): %.4f\t\t%s (%.2f): %.4f" % (
                    row.home, row.hbet, hprob, row.away, row.abet, aprob))
                print("Home Bet: %s\t\t\tAway Bet: %s\t\t" % (hbet, abet))
                print("Predicted: %s\t\t\tWinner: %s\t\t\tPredictions: %d/%d\t\tPercentage: %.4f" % (
                    predict, winner, npredict, ntotal, (npredict / ntotal)))
                try:
                    print("Number of bets: %d\t\tNum of wins: %d\t\tPercentage: %.4f" % (nbets, nwins, (nwins / nbets)))
                except ZeroDivisionError:
                    print("No Bets")
                print("Bankroll: %.2f" % bankroll)
                print()

        # Testing Summary
        print("Predicted: %d/%d\t\tPercentage: %.4f" % (npredict, ntotal, (npredict / ntotal)))
        try:
            print("Number of bets: %d\t\tNum of wins: %d\t\tPercentage: %.4f" % (nbets, nwins, (nwins / nbets)))
        except ZeroDivisionError:
            print("No Bets")
        print("Bankroll: %.2f" % bankroll)


class DixonColes(Basketball):
    """
    Subclass for the Dixon and Coles model which uses the full time scores of each match.
    """

    def __init__(self, test, season=None, month=None, nteams=4, ngames=4, nmargin=10, xi=0):
        """
        Initialize DixonColes instance.  Can be a test dataset where the teams are structured from best to worst
        based on results or using NBA seasons.  If an ID is given, the abilities will be loaded from the database.

        :param test: Fabricated Set
        :param season: NBA Season(s)
        :param month: Calendar Month(s)
        :param nteams: Number of teams for test set
        :param ngames: Number of games played between teams for test set
        :param nmargin: Winning Margin in test set
        """

        super().__init__(test, season, month, nteams, ngames, nmargin)

        if test:
            self.dataset = datasets.create_test_set(nteams, ngames, nmargin, False)
        else:
            self.dataset = datasets.dc_dataframe(self.teams, season, month, False)

        # Initial Guess for the minimization
        a0 = dr.initial_guess(0, self.nteams)

        # Time the optimization
        start = time.time()

        # Minimize the likelihood function
        self.opt = minimize(dr.dixon_coles, x0=a0,
                            args=(self.dataset, self.nteams, self.dataset['week'].max() + 28, xi),
                            constraints=self.con, method='SLSQP')

        end = time.time()
        print("Time: %f" % (end - start))

        # Scipy minimization requires a numpy array for all abilities, so convert them to readable dict
        self.abilities = dr.convert_abilities(self.opt.x, 0, self.teams)

    def find_time_param(self):
        """
        In the Dixon and Coles model, they determine a weighting function to make sure more recent results are more
        relevant in the model.  The function they chose is exp(-Xi * t).  A larger value of Xi will give a higher weight
        to more recent results.  We require a Xi where the overall predictive capability of the model is maximized. To
        do so, we must acquire team abilities with different Xi values and find the estimates with those Xi values.

        t values are weeks.
        355 is the beginning of the 2017 nba season

        :return: Different time values
        """

        s = 0

        dataset = datasets.dc_dataframe(self.teams, season=2017)

        # Determine the points of the Xi function
        for row in dataset.itertuples():

            # Poisson Means
            hmean = self.opt.x[row.home] * self.opt.x[row.away + self.nteams] * self.opt.x[self.nteams * 2]
            amean = self.opt.x[row.away] * self.opt.x[row.home + self.nteams]

            # Calculate probabilities
            prob = 0
            for h in range(60, 140):
                for a in range(60, 140):

                    if h > a and row.hpts > row.apts:
                        prob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))
                    elif h < a and row.hpts < row.apts:
                        prob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))

            s += np.log(prob)

        return s


class DixonRobinson(Basketball):
    """
    Subclass for the Dixon and Robinson model which uses the time each point was scored rather than only full time
    scores.
    """

    def __init__(self, test, model, season=None, month=None, nteams=4, ngames=4, nmargin=10):
        """
        Initialize DixonRobinson instance.  Can be a test dataset where the teams are structured from best to worst
        based on results or using NBA seasons.  If an ID is given, the abilities will be loaded from the database.

        :param test: Fabricated Set
        :param model: Dixon and Robinson model (1 to 4)
        :param season: NBA Season(s)
        :param month: Calendar Month(s)
        :param nteams: Number of teams for test set
        :param ngames: Number of games played between teams for test set
        :param nmargin: Winning Margin in test set
        """

        super().__init__(test, season, month, nteams, ngames, nmargin)

        if test:
            self.dataset = datasets.create_test_set(nteams, ngames, nmargin, True)
        else:
            self.dataset = datasets.dr_dataframe(model, self.teams, season, month)

        # Initial Guess for the minimization
        a0 = dr.initial_guess(model, self.nteams)

        # Time the optimization
        start = time.time()

        # Minimize the likelihood function
        self.opt = minimize(dr.dixon_robinson, x0=a0, args=(self.dataset, self.nteams, model),
                            constraints=self.con)

        end = time.time()
        print("Time: %f" % (end - start))

        # Scipy minimization requires a numpy array for all abilities, so convert them to readable dict
        self.abilities = dr.convert_abilities(self.opt.x, model, self.teams)
