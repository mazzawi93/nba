import time

import numpy as np
from scipy.optimize import minimize
from scipy.stats import poisson

from db import datasets
from db import process_utils
from models import dixon_robinson as dr
from models.game_prediction import dixon_prediction


class Basketball:
    """
    Basketball class used to manipulate team abilities and simulate upcoming seasons
    """

    def __init__(self, season):
        """
        Initialize Basketball class by setting class variables

        :param season: NBA Season(s)
        """

        self.nteams = 30
        self.season = season
        self.teams = process_utils.name_teams(False, 30)

        self.con = [{'type': 'eq', 'fun': dr.attack_constraint, 'args': (100, self.nteams,)},
                    {'type': 'eq', 'fun': dr.defense_constraint, 'args': (1, self.nteams,)}]

        self.abilities = None

    def test_model(self, season=None):
        """
        Test the optimized model against a testing set and apply a betting strategy

        :param season: NBA Season(s)
        :return: Number of correct predictions and number of games by percentage
        """

        # If it is nba data we are working with get current season, else create a testing set with the same
        # parameters as the training set
        if season is None:
            season = 2017

        ncorrect = dixon_prediction(season, self.abilities)

        return ncorrect


class DixonColes(Basketball):
    """
    Subclass for the Dixon and Coles model which uses the full time scores of each match.
    """

    def __init__(self, season, xi=0):
        """
        Initialize DixonColes instance.

        :param season: NBA Season(s)
        :param xi: Recent match weight
        """

        super().__init__(season)

        self.dataset = datasets.dc_dataframe(self.teams, season)

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

        # SciPy minimization requires a numpy array for all abilities, so convert them to readable dict
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

    def __init__(self, season, model=1):
        """
        Initialize DixonRobinson instance.

        :param model: Dixon and Robinson model (1 to 4)
        :param season: NBA Season(s)
        """

        super().__init__(season)

        self.dataset = datasets.dr_dataframe(model, self.teams, season)

        # Initial Guess for the minimization
        a0 = dr.initial_guess(model, self.nteams)

        # Time the optimization
        start = time.time()

        # Minimize the likelihood function
        self.opt = minimize(dr.dixon_robinson, x0=a0, args=(self.dataset, self.nteams, model),
                            constraints=self.con)

        end = time.time()
        print("Time: %f" % (end - start))

        # SciPy minimization requires a numpy array for all abilities, so convert them to readable dict
        self.abilities = dr.convert_abilities(self.opt.x, model, self.teams)
