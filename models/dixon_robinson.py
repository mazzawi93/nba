from scipy.stats import poisson
import numpy as np


def attack_constraint(params, nteams):
    """
    Attack parameter constraint for the likelihood functions
    The Mean of the attack parameters must equal 100

    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[:nteams]) / nteams - 100


def dixon_coles(params, games, teams):
    """
    This is the likelihood function for the Dixon Coles model adapted for basketball.
    :param params: Dixon-Coles Model Paramters
    :param games: DataFrame of games
    :param teams: List of teams
    :return: Log Likelihood from the Dixon-Coles Model
    """

    # Likelihood
    total = 0

    # Number of teams
    num = len(teams)

    # Iterate through each game
    for row in games.itertuples():

        # Since the parameters are in a numpy array, must find the index corresponding to the team
        for i in [i for i, x in enumerate(teams) if x == row.home]:
            h = i

        for i in [i for i, x in enumerate(teams) if x == row.away]:
            a = i

        # Home and Away Poisson intensities
        hmean = params[num * 2] * params[h] * params[a + num]
        amean = params[h + num] * params[a]

        # Log Likelihood
        total += poisson.logpmf(row.home_pts, hmean) + poisson.logpmf(row.away_pts, amean)

    return -total


def dixon_robinson(params, games, teams, model):
    """
    The likelihood function for the dixon-robinson model adapted for basketball.  This function is used
    by the SciPy Minimize function which requires the unknown parameters to be in a 1d numpy array.

    There are different models that get more and more complex.

    Model 1: Base Model only using team attack and defence (+ Home Advantage)
    Model 2: Define the time parameters rho.  For the football model there are two parameters for added time at
    half and at the end of the game.  For this basketball implementation, 4 variables are used for each quarter.
    Model 3: Define 4 parameters for when the home/away team are winning/losing

    :param params: Dixon-Robinson Model Parameters
    :param games: DataFrame of games with point timestamps
    :param teams: List of teams
    :param model: Which Dixon-Robinson Model (See Above)
    :return: Log Likelihood from Dixon-Robinson Model
    """

    # Likelihood
    total = 0

    # Number of teams
    num = len(teams)

    # Iterate through each game
    for row in games.itertuples():

        h, a = 0, 0

        # Since the parameters are in a numpy array, must find the index corresponding to the team
        for i in [i for i, x in enumerate(teams) if x == row.home]:
            h = i
        for i in [i for i, x in enumerate(teams) if x == row.away]:
            a = i

        # Home and Away Points
        hp, ap = 0, 0
        hlast4, alast4 = 0, 0
        havg, aavg = 0, 0
        check = list(range(4, 52, 4))
        period = 1

        # Match likelihood
        match_like = 0

        for point in row.time:

            time = 1
            scoreline = 1

            score = int(point['points'])
            time_stamp = float(point['time'])

            # Add Time Parameter to model
            if model >= 2:

                # First Quarter
                if (11 / 48) < time_stamp <= (12 / 48):
                    time = params[num * 2 + 1]
                # Second Quarter (Half Time)
                elif (23 / 48) < time_stamp <= (24 / 48):
                    time = params[num * 2 + 2]
                # Third Quarter
                elif (35 / 48) < time_stamp <= (36 / 48):
                    time = params[num * 2 + 3]
                # Fourth Quarter (End of Game)
                elif (47 / 48) < time_stamp <= (48 / 48):
                    time = params[num * 2 + 4]
                else:
                    time = 1

            if model == 3 or model == 4:
                if time_stamp >= (check[period] / 48):
                    havg = hlast4 / 4
                    aavg = alast4 / 4
                    hlast4, alast4 = 0, 0

                    period += 1

            # If the home team scored add
            if point['home'] == 1:

                if model == 5:
                    time_vary = params[num*2 + 5]

                # Add to current score
                hp += score
                point = hp

                # Add winning/losing parameter
                if model == 3 or model == 4:
                    hlast4 += score
                    if havg - aavg >= 1:
                        scoreline = params[num * 2 + 5]
                    elif havg - aavg <= -1:
                        scoreline = params[num * 2 + 6]

                    if model == 4:
                        if havg - aavg >= 3:
                            scoreline = params[num * 2 + 9]
                        elif havg - aavg <= -3:
                            scoreline = params[num * 2 + 10]
                        elif havg - aavg >= 2:
                            scoreline = params[num * 2 + 11]
                        elif havg - aavg <= -2:
                            scoreline = params[num * 2 + 12]

                # Poisson mean
                mean = params[h] * params[a + num] * params[num * 2] * time * scoreline
            # Away Team scored
            else:

                if model == 5:
                    time_vary = params[num * 2 + 6]

                # Add to current score
                ap += score
                point = ap

                # Add winning/losing parameter
                if model == 3 or model == 4:
                    alast4 += score
                    if aavg - havg >= 1:
                        scoreline = params[num * 2 + 7]
                    elif aavg - havg <= -1:
                        scoreline = params[num * 2 + 8]

                    if model == 4:
                        if aavg - havg >= 3:
                            scoreline = params[num * 2 + 13]
                        elif aavg - havg <= -3:
                            scoreline = params[num * 2 + 14]
                        elif aavg - havg >= 2:
                            scoreline = params[num * 2 + 15]
                        elif aavg - havg <= -2:
                            scoreline = params[num * 2 + 16]

                # Poisson mean
                mean = params[h + num] * params[a] * time * scoreline

            # Add to log likelihood
            match_like += poisson.logpmf(point, mean)

            if model == 5:
                match_like += np.log(time_vary * time_stamp)

        # Total Log Likelihood
        total += match_like - poisson.logpmf(hp, (params[h] * params[a + num] * params[num * 2])) - poisson.logpmf(
            ap, (params[h + num] * params[a]))

    return -total
