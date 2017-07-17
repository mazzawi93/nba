import numpy as np
from scipy.stats import poisson


def attack_constraint(params, constraint, nteams):
    """
    Attack parameter constraint for the likelihood functions
    The Mean of the attack parameters must equal 100

    :param constraint: The mean for attack
    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[:nteams]) / nteams - constraint


def defense_constraint(params, constraint, nteams):
    """
    Attack parameter constraint for the likelihood functions
    The Mean of the attack parameters must equal 100

    :param constraint: Mean for defense
    :param params: Team Parameters (Attack, Defense and Home Rating)
    :param nteams: The number of teams
    :return: The mean of the attack - 100
    """

    return sum(params[nteams:nteams * 2]) / nteams - constraint


def initial_guess(model, nteams):
    """
    Create an initial guess for the minimization function
    :param model: The model implemented (0: DC, 1: Base DR model, 2: Time Parameters, 3: winning/losing)
    :param nteams: The number of teams
    :return: Numpy array of team abilities (Attack, Defense) and Home Advantage and other factors
    """

    # Attack and Defence parameters
    att = np.full((1, nteams), 100)
    defense = np.full((1, nteams), 1)
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

        # Team indexes
        h = teams.index(row.home)
        a = teams.index(row.away)

        # Home and Away Poisson intensities
        hmean = params[num * 2] * params[h] * params[a + num]
        amean = params[h + num] * params[a]

        # Log Likelihood
        total += poisson.logpmf(row.hpts, hmean) + poisson.logpmf(row.apts, amean)

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

        h = teams.index(row.home)
        a = teams.index(row.away)

        # Home and Away Stats
        hp, ap = 0, 0
        hlast4, alast4 = 0, 0
        havg, aavg = 0, 0

        # Minute Interval Check
        check = range(4, 52, 4)

        quarter = 1
        run = 1

        # Match likelihood
        match_like = 0

        for point in row.time:

            # Time Parameter for Dixon Robinson model
            time_param = 1
            run = 1

            score = point['points']
            home = point['home']
            curr_min = point['time']

            # Add minute Parameter to model
            if model >= 2:

                # Determine if end of quarter
                if 11 < curr_min <= 12:
                    time_param = params[num * 2 + 1]
                elif 23 < curr_min <= 24:
                    time_param = params[num * 2 + 2]
                elif 35 < curr_min <= 36:
                    time_param = params[num * 2 + 3]
                elif 47 < curr_min <= 48:
                    time_param = params[num * 2 + 4]
                else:
                    time_param = 1

            if model == 3 or model == 4:
                if curr_min > check[quarter]:
                    havg = hlast4 / 4
                    aavg = alast4 / 4
                    hlast4, alast4 = 0, 0

                    quarter += 1

            # If the home team scored
            if home == 1:

                # Add to current score
                hp += score

                # Add winning/losing parameter
                if model == 3 or model == 4:
                    hlast4 += score
                    if havg - aavg >= 1:
                        run = params[num * 2 + 5]
                    elif havg - aavg <= -1:
                        run = params[num * 2 + 6]

                    if model == 4:
                        if havg - aavg >= 3:
                            run = params[num * 2 + 9]
                        elif havg - aavg <= -3:
                            run = params[num * 2 + 10]
                        elif havg - aavg >= 2:
                            run = params[num * 2 + 11]
                        elif havg - aavg <= -2:
                            run = params[num * 2 + 12]

                # Poisson mean
                mean = params[h] * params[a + num] * params[num * 2] * time_param * run
                match_like += (poisson.logpmf(row.hpts, mean)) * score

            # Away Team scored
            else:

                # Add to current score
                ap += score

                # Add winning/losing parameter
                if model == 3 or model == 4:
                    alast4 += score
                    if aavg - havg >= 1:
                        run = params[num * 2 + 7]
                    elif aavg - havg <= -1:
                        run = params[num * 2 + 8]

                    if model == 4:
                        if aavg - havg >= 3:
                            run = params[num * 2 + 13]
                        elif aavg - havg <= -3:
                            run = params[num * 2 + 14]
                        elif aavg - havg >= 2:
                            run = params[num * 2 + 15]
                        elif aavg - havg <= -2:
                            run = params[num * 2 + 16]

                # Poisson mean
                mean = params[h + num] * params[a] * time_param * run

                # Add to log likelihood
                match_like += (poisson.logpmf(row.apts, mean)) * score

        if model >= 2:
            time_param = params[num * 2 + 4]
        else:
            time_param = 1

        hmean = params[h] * params[a + num] * params[num * 2] * time_param * run
        amean = params[h + num] * params[a] * time_param * run

        # Total Log Likelihood
        total += match_like - poisson.logpmf(row.hpts, hmean) - poisson.logpmf(row.apts, amean)

    return -total
