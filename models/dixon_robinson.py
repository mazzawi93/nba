from scipy.stats import poisson


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

        # Match likelihood
        match_like = 0

        # Iterate through each point scored
        for point in row.time:

            time = 1
            scoreline = 1

            # Add Time Parameter to model
            if model >= 2:
                time_stamp = float(point['time'])

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

            # If the home team scored add
            if point['home'] == 1:

                # Add to current score
                hp += int(point['points'])
                point = hp

                # Add winning/losing paramter
                if model >= 3:
                    if hp > ap:
                        scoreline = params[num * 2 + 5]
                    elif hp < ap:
                        scoreline = params[num * 2 + 6]

                # Poisson mean
                mean = params[h] * params[a + num] * params[num * 2] * time * scoreline
            # Away Team scored
            else:

                # Add to current score
                ap += int(point['points'])
                point = ap

                # Add winning/losing paramter
                if model >= 3:
                    if ap > hp:
                        scoreline = params[num * 2 + 7]
                    elif ap < hp:
                        scoreline = params[num * 2 + 8]

                # Poisson mean
                mean = params[h + num] * params[a] * time * scoreline

            # Add to log likelihood
            match_like += poisson.logpmf(point, mean)

        # Total Log Likelihood
        total += match_like - poisson.logpmf(hp, (params[h] * params[a + num] * params[num * 2])) - poisson.logpmf(
            ap, (params[h + num] * params[a]))

    return -total
