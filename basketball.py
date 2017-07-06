from bson.objectid import ObjectId
from pymongo import MongoClient
from scipy.optimize import minimize
from scipy.stats import poisson
import numpy as np
from db import datasets
from db import process_utils
from models import dixon_robinson as dr


class Basketball:
    def __init__(self, model, season=None, month=None, load=False, _id=None):

        if season is None:
            season = 2016

        # Dixon Coles dataset is different
        if model == 0:
            self.dataset = datasets.dc_dataframe(season, month, False)
        else:
            self.dataset = datasets.game_scores(season=season, month=month)

        # Dataset information
        self.teams = process_utils.name_teams(True)
        self.nteams = 30
        self.season = season

        if load:
            self.load_abilities(_id)
        else:

            # Initial Guess for the minimization
            a0 = dr.initial_guess(model, self.nteams)

            # Minimize Constraint
            con = {'type': 'eq', 'fun': dr.attack_constraint, 'args': (100, self.nteams,)}

            # Minimize the likelihood function
            if model == 0:
                self.opt = minimize(dr.dixon_coles, x0=a0, args=(self.dataset, self.teams, self.dataset.week.max()),
                                    constraints=con)
            else:
                self.opt = minimize(dr.dixon_robinson, x0=a0, args=(self.dataset, self.teams, model),
                                    constraints=con)

            # Scipy minization requires a numpy array for all abilities, so convert them to readable dict
            self.abilities = self.convert_abilities(self.opt.x, model)

    def find_time_param(self):

        time = np.arange(0, 0.025, 0.005)

        # Initial Guess for the minimization
        a0 = dr.initial_guess(0, self.nteams)

        # Minimize Constraint
        con = {'type': 'eq', 'fun': dr.attack_constraint, 'args': (100, self.nteams,)}

        s = np.zeros(5)
        ab = []
        i = 0
        for t in time:
            # Minimize the likelihood function
            opt = minimize(dr.dixon_coles, x0=a0, args=(self.dataset, self.teams, self.dataset.week.max(), t),
                           constraints=con)

            abilities = self.convert_abilities(opt.x, 0)
            ab.append(abilities)

            for row in self.dataset.itertuples():
                # Poisson Means
                hmean = abilities[row.home]['att'] * abilities[row.away]['def'] * abilities['home']
                amean = abilities[row.away]['att'] * abilities[row.home]['def']

                # Calculate probabilities
                prob = 0
                for h in range(60, 140):
                    for a in range(60, 140):

                        if h > a and row.hpts > row.apts:
                            prob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))
                        elif h < a and row.hpts < row.apts:
                            prob += (poisson.pmf(mu=hmean, k=h) * poisson.pmf(mu=amean, k=a))

                s[i] += np.log(prob)

            i += 1

        return ab, s

    def convert_abilities(self, opt, model):
        """
        Convert the numpy abilities array into a more usable dict
        :param opt: Abilities from optimization
        :param model: Model number determines which parameters are included
        """
        abilities = {'model': model}

        i = 0

        # Attack and defense
        for team in self.teams:
            abilities[team] = {
                'att': opt[i],
                'def': opt[i + self.nteams]
            }
            i += 1

        # Home Advantage
        abilities['home'] = opt[self.nteams * 2]

        # Time parameters
        if model >= 2:
            abilities['time'] = {
                'q1': opt[self.nteams * 2 + 1],
                'q2': opt[self.nteams * 2 + 2],
                'q3': opt[self.nteams * 2 + 3],
                'q4': opt[self.nteams * 2 + 4]
            }

        if model == 3:
            abilities['lambda'] = {
                '+1': opt[self.nteams * 2 + 5],
                '-1': opt[self.nteams * 2 + 6],
            }
            abilities['mu'] = {
                '+1': opt[self.nteams * 2 + 7],
                '-1': opt[self.nteams * 2 + 8]
            }
        elif model == 4:
            abilities['lambda'] = {
                '+1': opt[self.nteams * 2 + 5],
                '-1': opt[self.nteams * 2 + 6],
                '+2': opt[self.nteams * 2 + 11],
                '-2': opt[self.nteams * 2 + 12],
                '+3': opt[self.nteams * 2 + 9],
                '-3': opt[self.nteams * 2 + 10],
            }
            abilities['mu'] = {
                '+1': opt[self.nteams * 2 + 7],
                '-1': opt[self.nteams * 2 + 8],
                '+2': opt[self.nteams * 2 + 15],
                '-2': opt[self.nteams * 2 + 16],
                '+3': opt[self.nteams * 2 + 13],
                '-3': opt[self.nteams * 2 + 14]
            }

        if model == 5:
            abilities['time']['home'] = opt[self.nteams * 2 + 5]
            abilities['time']['away'] = opt[self.nteams * 2 + 6]

        return abilities

    def test_model(self, season=None, month=None, display=False):
        """
        Test the optimized model against a testing set
        :param season: NBA Season
        :return: Accuracy of the model
        """

        # If it is nba data we are working with get current season, else create a testing set with the same
        # parameters as the training set
        if season is None:
            season = [2017]

        if self.abilities['model'] == 0:
            test = datasets.dc_dataframe(season, month, bet=True)
        else:
            test = datasets.game_scores(season, month, bet=True)

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

        print("Predicted: %d/%d\t\tPercentage: %.4f" % (npredict, ntotal, (npredict / ntotal)))
        try:
            print("Number of bets: %d\t\tNum of wins: %d\t\tPercentage: %.4f" % (nbets, nwins, (nwins / nbets)))
        except ZeroDivisionError:
            print("No Bets")
        print("Bankroll: %.2f" % bankroll)

    def store_abilities(self):
        """
        Store team abilities in MongoDB
        """

        client = MongoClient()
        db = client.basketball
        collection = db.abilities

        abilities = self.abilities
        abilities['season'] = self.season
        collection.insert(abilities)

        client.close()

    def load_abilities(self, _id):
        """
        Load team abilities from mongoDB
        :param _id: MongoDB id
        """

        client = MongoClient()
        db = client.basketball
        collection = db.abilities

        ab = collection.find_one({'_id': ObjectId(_id)})

        self.abilities = ab
        client.close()
